"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { api, Recommendation } from "@/lib/api";

const CATEGORIES = [
  { id: "all", label: "All", icon: "⌕" },
  { id: "movie", label: "Movies", icon: "🎬" },
  { id: "anime", label: "Anime", icon: "✦" },
  { id: "tv", label: "TV Shows", icon: "▣" },
  { id: "game", label: "Games", icon: "◉" },
  { id: "book", label: "Books", icon: "▰" },
  { id: "video", label: "Videos", icon: "▶" },
  { id: "news", label: "News", icon: "⌁" },
] as const;

type Mode = "ai" | "web";
type SearchResult = { title: string; url: string; snippet?: string; source?: string; provider?: string };
type ChatResult = { answer: string; mode: string; facts?: string[]; recommendations?: { title: string; type: string; score: number; reason: string }[]; assumptions?: string[] };
type WebPayload = { query: string; results: SearchResult[] };

const suffix: Record<string, string> = {
  movie: "movies",
  anime: "anime",
  tv: "TV shows",
  game: "video games",
  book: "books",
  video: "site:youtube.com",
  news: "news",
};

function scopedQuery(category: string, query: string) {
  return category === "all" ? query : `${query} ${suffix[category] || ""}`.trim();
}

export default function SearchExperience() {
  const pathname = usePathname();
  const [homeActive, setHomeActive] = useState(true);
  const [mode, setMode] = useState<Mode>("ai");
  const [category, setCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [answer, setAnswer] = useState<ChatResult | null>(null);
  const [localRecs, setLocalRecs] = useState<Recommendation[]>([]);
  const [autoResults, setAutoResults] = useState<Record<string, SearchResult[]>>({});
  const [busy, setBusy] = useState(false);
  const [booting, setBooting] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  const categoryLabel = useMemo(() => CATEGORIES.find((x) => x.id === category)?.label || "All", [category]);

  useEffect(() => {
    if (pathname !== "/") return;
    const update = () => {
      const active = document.querySelector(".sidebar .nav-item.active span")?.textContent?.trim();
      setHomeActive(!active || active === "Home");
    };
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, [pathname]);

  useEffect(() => {
    if (pathname !== "/" || !homeActive) return;
    let cancelled = false;
    (async () => {
      setBooting(true);
      try {
        const local = await api<Recommendation[]>("/recommendations?limit=12");
        if (!cancelled) setLocalRecs(local || []);
        if (!local?.length) {
          const defaults = [
            ["movie", "best movies to watch 2026"],
            ["anime", "best anime to watch 2026"],
            ["game", "best single player games 2026"],
            ["book", "best books to read 2026"],
          ] as const;
          const pairs = await Promise.all(defaults.map(async ([key, q]) => {
            try {
              const payload = await api<WebPayload>("/research/search", { method: "POST", body: JSON.stringify({ query: q }) });
              return [key, (payload.results || []).slice(0, 4)] as const;
            } catch { return [key, []] as const; }
          }));
          if (!cancelled) setAutoResults(Object.fromEntries(pairs));
        }
      } catch {
        // Search remains usable even when the local backend is temporarily unavailable.
      } finally {
        if (!cancelled) setBooting(false);
      }
    })();
    return () => { cancelled = true; };
  }, [homeActive, pathname]);

  useEffect(() => {
    if (pathname !== "/" || !homeActive) return;
    const interceptLegacyHomeSearch = (event: Event) => {
      const target = event.target as HTMLElement | null;
      if (!target?.closest(".ask-box")) return;
      event.preventDefault();
      event.stopPropagation();
      const input = target.closest("form")?.querySelector("input") as HTMLInputElement | null;
      const value = input?.value?.trim();
      if (value) {
        setQuery(value);
        void runSearch(undefined, value);
      }
    };
    document.addEventListener("submit", interceptLegacyHomeSearch, true);
    return () => document.removeEventListener("submit", interceptLegacyHomeSearch, true);
  });

  if (pathname !== "/" || !homeActive) return null;

  async function runSearch(event?: FormEvent, forcedQuery?: string) {
    event?.preventDefault();
    const text = (forcedQuery ?? query).trim();
    if (!text || busy) return;
    setQuery(text);
    setBusy(true);
    setSearched(true);
    setError("");
    setAnswer(null);
    try {
      const web = await api<WebPayload>("/research/search", {
        method: "POST",
        body: JSON.stringify({ query: scopedQuery(category, text) }),
      });
      const webResults = web.results || [];
      setResults(webResults);
      if (mode === "ai") {
        const evidence = webResults.slice(0, 8).map((r, i) => `${i + 1}. ${r.title}\n${r.snippet || ""}\n${r.url}`).join("\n\n");
        const prompt = `${text}\n\nUse these fresh public web search results as evidence. Do not invent facts and distinguish web information from personal-library information:\n${evidence}`;
        const ai = await api<ChatResult>("/chat", { method: "POST", body: JSON.stringify({ message: prompt }) });
        setAnswer(ai);
      }
    } catch (e) {
      setResults([]);
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  const quickSearch = (value: string, nextCategory = category) => {
    setCategory(nextCategory);
    setQuery(value);
    void runSearch(undefined, value);
  };

  const openGoogle = () => {
    const text = query.trim();
    if (!text) return;
    window.open(`https://www.google.com/search?q=${encodeURIComponent(scopedQuery(category, text))}`, "_blank", "noopener,noreferrer");
  };

  const showAuto = !searched && !localRecs.length;

  return (
    <section className="search-experience" aria-label="Manu AI global search">
      <div className="search-topbar">
        <div className="search-brand"><span>M</span><strong>Manu</strong><b>AI</b></div>
        <div className="search-top-actions"><button type="button" onClick={() => setMode("web")}>Web</button><button type="button" onClick={() => setMode("ai")}>AI</button><div className="search-avatar">M</div></div>
      </div>

      <div className="search-hero">
        <div className="search-kicker">PERSONAL SEARCH & DISCOVERY</div>
        <h1>Manu<span>AI</span></h1>
        <p>Search the web. Ask your local AI. Find what you actually want.</p>
        <form className="global-search" onSubmit={runSearch}>
          <span className="search-icon">⌕</span>
          <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search anything or ask Manu AI…" aria-label="Search anything" />
          <div className="mode-toggle" aria-label="Search mode">
            <button type="button" className={mode === "ai" ? "active" : ""} onClick={() => setMode("ai")}>✦ AI</button>
            <i />
            <button type="button" className={mode === "web" ? "active" : ""} onClick={() => setMode("web")}>G Google</button>
          </div>
          <button className="global-submit" type="submit" disabled={busy}>{busy ? "…" : "→"}</button>
        </form>
        <div className="category-strip">
          {CATEGORIES.map((item) => <button key={item.id} type="button" className={category === item.id ? "active" : ""} onClick={() => setCategory(item.id)}>{item.icon} {item.label}</button>)}
        </div>
        <div className="search-shortcuts">
          <button type="button" onClick={() => quickSearch("best movies to watch tonight", "movie")}>🎬 Movies</button>
          <button type="button" onClick={() => quickSearch("best anime to watch", "anime")}>✦ Anime</button>
          <button type="button" onClick={() => quickSearch("best games to play", "game")}>◉ Games</button>
          <button type="button" onClick={() => quickSearch("best books to read", "book")}>▰ Books</button>
          <button type="button" onClick={() => quickSearch("latest technology news", "news")}>⌁ News</button>
          <button type="button" onClick={openGoogle}>Open Google ↗</button>
        </div>
      </div>

      {error && <div className="search-error">{error}. The search page is still available; check that the backend is running on port 8000.</div>}
      {searched ? (
        <div className="search-content">
          {answer && mode === "ai" && <article className="search-ai-answer"><div className="answer-label">MANU AI · WEB-AUGMENTED LOCAL</div><p>{answer.answer}</p>{!!answer.facts?.length && <div className="answer-facts">{answer.facts.slice(0, 5).map((f) => <span key={f}>✓ {f}</span>)}</div>}</article>}
          <section className="web-results-block"><div className="results-title"><div><span>SEARCH RESULTS</span><h2>{results.length ? `Results for “${query}”` : "No results found"}</h2></div><div className="result-actions"><span>{categoryLabel}</span><button type="button" onClick={openGoogle}>Google ↗</button></div></div>{results.map((r) => <a className="search-result-card" key={`${r.url}-${r.title}`} href={r.url} target="_blank" rel="noreferrer"><small>{r.url.replace(/^https?:\/\//, "").split("/")[0]}</small><h3>{r.title}</h3><p>{r.snippet || "Open this result."}</p></a>)}</section>
        </div>
      ) : (
        <div className="discovery-content">
          {localRecs.length > 0 && <section><div className="results-title"><div><span>YOUR TASTE</span><h2>Recommended for you</h2></div></div><div className="recommendation-grid-search">{localRecs.slice(0, 8).map((r) => <article key={r.item.id}><strong>{r.item.title}</strong><p>{r.reasons?.[0] || "Selected from your local taste profile."}</p><small>{r.item.genres || r.item.media_type}</small></article>)}</div></section>}
          {showAuto && Object.entries(autoResults).map(([key, rows]) => rows.length > 0 && <section key={key} className="auto-section"><div className="results-title"><div><span>DISCOVER</span><h2>{key === "movie" ? "Movies you may like" : key === "anime" ? "Anime you may like" : key === "game" ? "Games you may like" : "Books you may like"}</h2></div><button type="button" onClick={() => quickSearch(`best ${key === "movie" ? "movies" : key} to watch`, key)}>Search more →</button></div><div className="auto-grid">{rows.map((r) => <a key={`${r.url}-${r.title}`} href={r.url} target="_blank" rel="noreferrer"><small>{r.url.replace(/^https?:\/\//, "").split("/")[0]}</small><h3>{r.title}</h3><p>{r.snippet || "Open result"}</p></a>)}</div></section>)}
          {booting && <div className="search-loading">Building your discovery feed…</div>}
        </div>
      )}
      <footer className="search-footer"><span>Private library stays local</span><span>Web search is on-demand</span><span>AI uses fresh public results when searching</span></footer>
    </section>
  );
}
