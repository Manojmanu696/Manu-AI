import { NextRequest, NextResponse } from "next/server";

type Result = { title: string; url: string; snippet: string; provider: string };

function clean(value: string) {
  return value.replace(/\s+/g, " ").replace(/&amp;/g, "&").replace(/&#x27;/g, "'").replace(/&quot;/g, '"').trim();
}

function categoryQuery(query: string, category: string) {
  const suffix: Record<string, string> = {
    movies: "movies film",
    anime: "anime",
    tv: "TV series shows",
    games: "video games",
    books: "books",
    videos: "videos",
    websites: "",
    all: "",
  };
  return `${query} ${suffix[category] || ""}`.trim();
}

function parseResults(html: string): Result[] {
  const results: Result[] = [];
  const blockRe = /<div[^>]+class="[^"]*result[^\"]*"[\s\S]*?<\/div>\s*<\/div>/gi;
  const blocks = html.match(blockRe) || [];

  for (const block of blocks) {
    const link = block.match(/<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/i);
    if (!link) continue;
    const href = link[1].replace(/&amp;/g, "&");
    const title = clean(link[2].replace(/<[^>]+>/g, " "));
    const snippetMatch = block.match(/class="[^"]*result__snippet[^"]*"[^>]*>([\s\S]*?)<\/[^>]+>/i);
    const snippet = clean((snippetMatch?.[1] || "").replace(/<[^>]+>/g, " "));
    if (title && /^https?:\/\//i.test(href)) results.push({ title, url: href, snippet, provider: "duckduckgo" });
    if (results.length >= 12) break;
  }

  if (results.length) return results;

  // Fallback parser for minor markup changes in the lightweight HTML endpoint.
  const anchors = [...html.matchAll(/<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi)];
  for (const match of anchors.slice(0, 12)) {
    const title = clean(match[2].replace(/<[^>]+>/g, " "));
    const url = match[1].replace(/&amp;/g, "&");
    if (title && /^https?:\/\//i.test(url)) results.push({ title, url, snippet: "", provider: "duckduckgo" });
  }
  return results;
}

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q")?.trim() || "";
  const category = request.nextUrl.searchParams.get("category") || "all";
  if (!q) return NextResponse.json({ query: "", results: [], provider: "duckduckgo" });

  try {
    const searchQuery = categoryQuery(q.slice(0, 300), category);
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
    if (!response.ok) throw new Error(`Search provider returned ${response.status}`);
    const html = await response.text();
    return NextResponse.json({ query: q, results: parseResults(html), provider: "duckduckgo" });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Search failed", query: q, results: [], provider: "duckduckgo" }, { status: 502 });
  }
}
