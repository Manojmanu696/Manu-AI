import { NextRequest, NextResponse } from "next/server";

type Result = { title: string; url: string; snippet: string; provider: string };

function clean(value: string) {
  return value.replace(/\s+/g, " ").replace(/&amp;/g, "&").replace(/&#x27;/g, "'").replace(/&quot;/g, '"').trim();
}

function categoryQuery(query: string, category: string) {
  const suffix: Record<string, string> = {
    movies: "movies film",
    movie: "movies film",
    anime: "anime",
    tv: "TV series shows",
    games: "video games",
    game: "video games",
    books: "books",
    book: "books",
    videos: "videos",
    video: "videos",
    websites: "",
    website: "",
    all: "",
  };
  return `${query} ${suffix[category] || ""}`.trim();
}

function parseDuck(html: string): Result[] {
  const results: Result[] = [];
  const anchors = [...html.matchAll(/<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi)];
  for (const match of anchors.slice(0, 12)) {
    const title = clean(match[2].replace(/<[^>]+>/g, " "));
    const url = match[1].replace(/&amp;/g, "&");
    if (title && /^https?:\/\//i.test(url)) results.push({ title, url, snippet: "", provider: "duckduckgo" });
  }
  return results;
}

function parseBing(html: string): Result[] {
  const results: Result[] = [];
  const blocks = html.match(/<li[^>]+class="[^"]*b_algo[^"]*"[\s\S]*?<\/li>/gi) || [];
  for (const block of blocks.slice(0, 12)) {
    const link = block.match(/<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/i);
    if (!link) continue;
    const title = clean(link[2].replace(/<[^>]+>/g, " "));
    const url = link[1].replace(/&amp;/g, "&");
    const p = block.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
    const snippet = clean((p?.[1] || "").replace(/<[^>]+>/g, " "));
    if (title && /^https?:\/\//i.test(url)) results.push({ title, url, snippet, provider: "bing" });
  }
  return results;
}

async function searchBing(query: string) {
  const url = `https://www.bing.com/search?q=${encodeURIComponent(query)}&cc=in&setlang=en`;
  const response = await fetch(url, {
    headers: { "user-agent": "Mozilla/5.0 ManuAI/1.0", accept: "text/html,application/xhtml+xml" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Bing returned ${response.status}`);
  return parseBing(await response.text());
}

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q")?.trim() || "";
  const category = request.nextUrl.searchParams.get("category") || "all";
  if (!q) return NextResponse.json({ query: "", results: [], provider: "bing" });

  const searchQuery = categoryQuery(q.slice(0, 300), category);

  try {
    const body = new URLSearchParams({ q: searchQuery, kl: "in-en", kp: "-1" });
    const response = await fetch("https://html.duckduckgo.com/html/", {
      method: "POST",
      headers: {
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "Mozilla/5.0 ManuAI/1.0",
        accept: "text/html,application/xhtml+xml",
      },
      body,
      cache: "no-store",
    });
    if (response.ok) {
      const results = parseDuck(await response.text());
      if (results.length) return NextResponse.json({ query: q, results, provider: "duckduckgo" });
    }
  } catch {
    // Fall through to Bing. The UI should never become unusable because one
    // public search provider rejects the server's IP.
  }

  try {
    const results = await searchBing(searchQuery);
    return NextResponse.json({ query: q, results, provider: "bing" });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Search failed", query: q, results: [], provider: "bing" },
      { status: 502 },
    );
  }
}
