"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { api, Recommendation } from "@/lib/api";
import { Icon } from "@/components/icons";

const CATEGORIES = [
  { id: "all", label: "All" },
  { id: "movie", label: "Movies" },
  { id: "anime", label: "Anime" },
  { id: "tv", label: "TV Shows" },
  { id: "game", label: "Games" },
  { id: "book", label: "Books" },
  { id: "video", label: "Videos" },
  { id: "news", label: "News" },
];

type SearchResult = { title: string; url: string; snippet?: string; provider?: string; source?: string };
type ChatResult = { answer: string; mode: string; facts?: string[]; recommendations?: { title: string; type: string; score: number; reason: string }[]; assumptions?: string[] };

function searchQueryFor(category: string, query: string) {
  const suffix: Record<string, string> = { movie: "movies", anime: "anime", tv: "TV shows", game: "video games", book: "books", video: "site:youtube.com", news: "news" };
  return category === "all" ? query : `${query} ${suffix[category] || ""}`.trim();
}

export default function GoogleHome() {
  const pathname = usePathname();
  const [mode, setMode] = useState<"ai" | "web">("ai");
  const [category, setCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [answer, setAnswer] = useState<ChatResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const categoryLabel = useMemo(() => CATEGORIES.find((x) => x.id === category)?.label || "All", [category]);

  useEffect(() => {
    if (pathname !== "/") return;
    let cancelled = false;
    (async () => { try {
      const local = category !== "all" && !["video", "news"].includes(category) ? await api<Recommendation[]>(`/recommendations?media_type=${encodeURIComponent(category)}&limit=6`) : await api<Recommendation[]>("/recommendations?limit=6");
      if (!cancelled) setRecommendations(local || []);
    } catch { /* the main app still works if the backend is offline */ } })();
    return () => { cancelled = true; };
  }, [category, pathname]);

  if (pathname !== "/") return null;

  const runSearch = async (event?: FormEvent, forcedQuery?: string) => {
    event?.preventDefault();
    const text = (forcedQuery ?? query).trim();
    if (!text) return;
    setQuery(text); setBusy(true); setError(""); setSearched(true);
    try {
      const webQuery = searchQueryFor(category, text);
      const [web, ai] = await Promise.all([
        api<{ query: string; results: SearchResult[] }>("/research/search", { method: "POST", body: JSON.stringify({ query: webQuery }) }),
        mode === "ai" ? api<ChatResult>("/chat", { method: "POST", body: JSON.stringify({ message: text }) }) : Promise.resolve(null),
      ]);
      setResults(web.results || []); setAnswer(ai);
      if (category !== "all" && !["video", "news"].includes(category)) setRecommendations(await api<Recommendation[]>(`/recommendations?media_type=${encodeURIComponent(category)}&limit=8`));
      else setRecommendations([]);
    } catch (e) { setError(e instanceof Error ? e.message : "Search failed"); setResults([]); }
    finally { setBusy(false); }
  };

  const quickSearch = (value: string) => { setQuery(value); void runSearch(undefined, value); };

  return <section className="google-home" aria-label="Manu AI search">
    <div className="google-home-top"><div className="google-brand"><span className="brand-dot">M</span><span>Manu</span><b>AI</b></div><div className="google-top-links"><button onClick={() => setMode("web")}>Web</button><button onClick={() => setMode("ai")}>AI</button><span className="mini-avatar">M</span></div></div>
    <div className="google-center">
      <p className="google-kicker">PERSONAL SEARCH & DISCOVERY</p><h1>Manu<span>AI</span></h1><p className="google-subtitle">Search the web. Ask AI. Find what you actually want.</p>
      <form className="google-search" onSubmit={runSearch}><Icon name="search" size={21}/><input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search the web or ask Manu AI anything…" aria-label="Search" /><div className="search-mode" aria-label="Search mode"><button type="button" className={mode === "ai" ? "selected" : ""} onClick={() => setMode("ai")}>✦ AI</button><span></span><button type="button" className={mode === "web" ? "selected" : ""} onClick={() => setMode("web")}>⌕ Web</button></div><button className="search-submit" aria-label="Search" disabled={busy}>{busy ? "…" : "→"}</button></form>
      <div className="category-strip" aria-label="Search category">{CATEGORIES.map((item) => <button key={item.id} className={category === item.id ? "active" : ""} onClick={() => setCategory(item.id)}>{item.label}</button>)}</div>
      {!searched && <div className="google-quick"><button onClick={() => quickSearch("best movies to watch tonight")}>🎬 Movies</button><button onClick={() => quickSearch("best anime to watch")}>✦ Anime</button><button onClick={() => quickSearch("best games to play")}>◉ Games</button><button onClick={() => quickSearch("best books to read")}>▰ Books</button><button onClick={() => quickSearch("latest technology news")}>⌁ News</button></div>}
    </div>
    {error && <div className="google-error">{error}. Make sure the Manu AI backend is running on port 8000.</div>}
    {searched && <div className="search-results-area">
      {answer && mode === "ai" && <article className="ai-search-answer"><div className="result-label">MANU AI · {answer.mode === "local" ? "LOCAL" : "ASSISTED"}</div><p>{answer.answer}</p>{!!answer.facts?.length && <div className="answer-facts">{answer.facts.slice(0, 4).map((fact) => <span key={fact}>✓ {fact}</span>)}</div>}</article>}
      {!!recommendations.length && <section className="taste-results"><div className="results-heading"><div><span className="result-label">FROM YOUR TASTE</span><h2>{categoryLabel} picks for you</h2></div></div><div className="taste-grid">{recommendations.map((r) => <article key={r.item.id} className="taste-card"><div className="taste-score">{r.score}</div><div><h3>{r.item.title}</h3><p>{r.reasons?.[0] || "Selected for your taste profile."}</p><small>{r.item.genres || categoryLabel}</small></div></article>)}</div></section>}
      <section className="web-results"><div className="results-heading"><div><span className="result-label">WEB RESULTS</span><h2>{results.length ? `Results for “${query}”` : "No results found"}</h2></div><span className="provider-pill">Web search</span></div>{results.map((r) => <a className="web-result" key={`${r.url}-${r.title}`} href={r.url} target="_blank" rel="noreferrer"><div className="result-url">{r.url.replace(/^https?:\/\//, "").split("/")[0]}</div><h3>{r.title}</h3><p>{r.snippet || "Open this result to view the page."}</p></a>)}</section>
    </div>}
    {!searched && recommendations.length > 0 && <section className="home-recommendations"><div className="results-heading"><div><span className="result-label">YOUR PERSONAL DISCOVERY</span><h2>Things you may like</h2></div></div><div className="taste-grid">{recommendations.slice(0, 6).map((r) => <article key={r.item.id} className="taste-card"><div className="taste-score">{r.score}</div><div><h3>{r.item.title}</h3><p>{r.reasons?.[0] || "A recommendation from your local taste engine."}</p><small>{r.item.genres || r.item.media_type}</small></div></article>)}</div></section>}
    <footer className="google-footer"><span>Private by design</span><span>Local library stays on your Mac</span><span>Web search is on-demand</span></footer>
  </section>;
}
