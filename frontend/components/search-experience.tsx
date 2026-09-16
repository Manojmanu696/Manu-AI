"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, Recommendation } from "@/lib/api";

type Mode = "ai" | "google";
type SearchResult = { title: string; url: string; snippet?: string; source?: string; provider?: string };
type ChatResult = { answer?: string; mode?: string; facts?: string[]; assumptions?: string[] };
type DiscoveryItem = {
  id: number; media_type: string; title: string; description?: string; genres?: string; tags?: string;
  release_year?: number | null; image_url?: string; imdb_rating?: number | null; runtime?: string;
  intensity?: string; ending_type?: string; ott_india?: string; seasons?: number | null; episodes?: number | null;
  episode_duration?: string; author?: string; reading_length?: string; gameplay_style?: string;
  player_modes?: string; difficulty?: string;
};
type DiscoveryResult = { item: DiscoveryItem; score: number; reasons: string[]; source?: string };

const CATEGORIES = [
  { id: "all", label: "All", icon: "⌕" }, { id: "movie", label: "Movies", icon: "🎬" },
  { id: "anime", label: "Anime", icon: "✦" }, { id: "tv", label: "TV Shows", icon: "▣" },
  { id: "game", label: "Games", icon: "◉" }, { id: "book", label: "Books", icon: "▰" },
  { id: "video", label: "Videos", icon: "▶" }, { id: "news", label: "News", icon: "⌁" },
] as const;
const suffix: Record<string, string> = { movie: "movies", anime: "anime", tv: "TV shows", game: "video games", book: "books", video: "site:youtube.com", news: "news" };
const genericQueries: Record<string, string[]> = {
  movie: ["movie", "movies", "film", "films", "watch", "recommendation", "recommendations"],
  anime: ["anime", "animes", "watch"], tv: ["tv", "show", "shows", "series", "watch"],
  game: ["game", "games", "gaming", "play"], book: ["book", "books", "read", "reading"],
};
function scopedQuery(category: string, query: string) { return category === "all" ? query : `${query} ${suffix[category] || ""}`.trim(); }
function isGenericMediaQuery(category: string, query: string) { const words = query.toLowerCase().split(/\s+/).filter(Boolean); const allowed = genericQueries[category] || []; return words.length > 0 && words.every((word) => allowed.includes(word)); }
function mediaLabel(type: string) { return ({ movie: "Movie", anime: "Anime", tv: "TV Show", game: "Game", book: "Book" } as Record<string, string>)[type] || type; }

export default function SearchExperience() {
  const [mode, setMode] = useState<Mode>("ai");
  const [category, setCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [answer, setAnswer] = useState<ChatResult | null>(null);
  const [localRecs, setLocalRecs] = useState<Recommendation[]>([]);
  const [discovery, setDiscovery] = useState<DiscoveryResult[]>([]);
  const [autoResults, setAutoResults] = useState<Record<string, SearchResult[]>>({});
  const [busy, setBusy] = useState(false);
  const [booting, setBooting] = useState(true);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const categoryLabel = useMemo(() => CATEGORIES.find((x) => x.id === category)?.label || "All", [category]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const local = await api<Recommendation[]>("/recommendations?limit=12");
        if (!cancelled) setLocalRecs(local || []);
        const defaults = [["movie", "best movies to watch tonight"], ["anime", "best anime to watch"], ["game", "best single player games"], ["book", "best books to read"]] as const;
        const pairs = await Promise.all(defaults.map(async ([key, q]) => {
          try {
            const payload = await api<{ results: SearchResult[] }>("/research/search", { method: "POST", body: JSON.stringify({ query: q }) });
            return [key, (payload.results || []).slice(0, 4)] as const;
          } catch { return [key, []] as const; }
        }));
        if (!cancelled) setAutoResults(Object.fromEntries(pairs));
      } finally { if (!cancelled) setBooting(false); }
    })();
    return () => { cancelled = true; };
  }, []);

  async function loadDiscovery(nextCategory: string, text: string) {
    if (!["movie", "anime", "tv", "game", "book"].includes(nextCategory)) { setDiscovery([]); return; }
    const params = new URLSearchParams({ media_type: nextCategory, limit: "12" });
    if (text && !isGenericMediaQuery(nextCategory, text)) params.set("query", text);
    try {
      let rows = await api<DiscoveryResult[]>(`/discover?${params.toString()}`);
      if (!rows.length && text && !isGenericMediaQuery(nextCategory, text)) {
        const broad = new URLSearchParams({ media_type: nextCategory, limit: "12" });
        rows = await api<DiscoveryResult[]>(`/discover?${broad.toString()}`);
      }
      setDiscovery(rows || []);
    } catch { setDiscovery([]); }
  }

  async function runSearch(event?: FormEvent, forcedQuery?: string, forcedCategory?: string) {
    event?.preventDefault();
    const text = (forcedQuery ?? query).trim();
    const activeCategory = forcedCategory ?? category;
    if (!text || busy) return;
    setQuery(text); setBusy(true); setSearched(true); setError(""); setAnswer(null); setResults([]);
    try {
      const web = await api<{ query: string; results: SearchResult[] }>("/research/search", { method: "POST", body: JSON.stringify({ query: scopedQuery(activeCategory, text) }) });
      await loadDiscovery(activeCategory, text);
      const webResults = web.results || []; setResults(webResults);
      if (mode === "ai") {
        const evidence = webResults.slice(0, 8).map((r, i) => `${i + 1}. ${r.title}\n${r.snippet || ""}\n${r.url}`).join("\n\n");
        const prompt = `${text}\n\nUse these fresh public web results as evidence. Give a concise useful answer. Do not invent facts. Personalise only from the local profile.\n${evidence}`;
        const ai = await api<ChatResult>("/chat", { method: "POST", body: JSON.stringify({ message: prompt }) });
        setAnswer(ai);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Search failed"); }
    finally { setBusy(false); }
  }

  const quickSearch = (value: string, nextCategory = category) => { setCategory(nextCategory); setQuery(value); void runSearch(undefined, value, nextCategory); };
  const openGoogle = () => { const text = query.trim(); if (!text) return; window.open(`https://www.google.com/search?q=${encodeURIComponent(scopedQuery(category, text))}`, "_blank", "noopener,noreferrer"); };

  return (
    <section className="search-experience" aria-label="Manu AI global search">
      <header className="search-topbar"><div className="search-brand"><span>M</span><strong>Manu</strong><b>AI</b></div><div className="search-top-actions"><button type="button" onClick={() => setMode("google")}>Google</button><button type="button" onClick={() => setMode("ai")}>AI</button><div className="search-avatar">M</div></div></header>
      <main className="search-hero">
        <div className="search-kicker">PERSONAL SEARCH & DISCOVERY</div><h1>Manu<span>AI</span></h1><p>One search box for the web, your library, and your personal AI.</p>
        <form className="global-search" onSubmit={runSearch}><span className="search-icon">⌕</span><input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search anything…" aria-label="Search anything" /><div className="mode-toggle" aria-label="Search mode"><button type="button" className={mode === "ai" ? "active" : ""} onClick={() => setMode("ai")}>✦ AI Search</button><i /><button type="button" className={mode === "google" ? "active" : ""} onClick={() => setMode("google")}>G Google</button></div><button className="global-submit" type="submit" disabled={busy}>{busy ? "…" : "→"}</button></form>
        <div className="category-strip">{CATEGORIES.map((item) => <button key={item.id} type="button" className={category === item.id ? "active" : ""} onClick={() => setCategory(item.id)}>{item.icon} {item.label}</button>)}</div><div className="search-hint">⌘ K to focus · Choose a type to get personalized cards</div>
      </main>
      {error && <div className="search-error">{error}</div>}
      {!searched ? (
        <div className="discovery-content">
          {localRecs.length > 0 && <section className="taste-section"><div className="results-title"><div><span>YOUR TASTE</span><h2>Recommended for you</h2></div><button type="button" onClick={() => quickSearch("movies I should watch", "movie")}>Explore movies →</button></div><div className="recommendation-grid-search">{localRecs.slice(0, 6).map((r) => <TasteCard key={r.item.id} recommendation={r} />)}</div></section>}
          {Object.entries(autoResults).map(([key, rows]) => rows.length > 0 && <section key={key} className="auto-section"><div className="results-title"><div><span>DISCOVER</span><h2>{key === "movie" ? "Movies you may like" : key === "anime" ? "Anime you may like" : key === "game" ? "Games you may like" : "Books you may like"}</h2></div><button type="button" onClick={() => quickSearch(`best ${key === "movie" ? "movies" : key} to watch`, key)}>Search more →</button></div><div className="auto-grid">{rows.map((r) => <WebCard key={`${r.url}-${r.title}`} result={r} />)}</div></section>)}
          {booting && <div className="search-loading">Building your personalized discovery feed…</div>}
        </div>
      ) : (
        <div className="search-content">
          {answer && mode === "ai" && <article className="search-ai-answer"><div className="answer-label">MANU AI · WEB-AUGMENTED</div><p>{answer.answer?.trim() || "I found fresh results. The cards below contain the relevant matches."}</p>{!!answer.facts?.length && <div className="answer-facts">{answer.facts.slice(0, 5).map((f) => <span key={f}>✓ {f}</span>)}</div>}</article>}
          {discovery.length > 0 && <section className="discovery-results"><div className="results-title"><div><span>PERSONALIZED {categoryLabel.toUpperCase()}</span><h2>Matches for “{query}”</h2></div><div className="result-actions"><span>{discovery.length} cards</span><button type="button" onClick={openGoogle}>Open Google ↗</button></div></div><div className="media-discovery-grid">{discovery.map((r) => <DiscoveryCard key={r.item.id} result={r} />)}</div></section>}
          <section className="web-results-block"><div className="results-title"><div><span>WEB RESULTS</span><h2>{results.length ? `Results for “${query}”` : "No web results"}</h2></div><div className="result-actions"><span>{categoryLabel}</span><button type="button" onClick={openGoogle}>Google ↗</button></div></div>{results.map((r) => <WebCard key={`${r.url}-${r.title}`} result={r} />)}{!results.length && !discovery.length && <div className="no-results-card">No matches came back. Try a broader query or open Google for the full web.</div>}</section>
        </div>
      )}
      <footer className="search-footer"><span>Private library stays local</span><span>Web search is on-demand</span><span>AI search uses fresh public results</span></footer>
    </section>
  );
}

function TasteCard({ recommendation }: { recommendation: Recommendation }) { const item = recommendation.item; return <article className="taste-card"><div className="taste-poster"><span>{item.media_type}</span><strong>{item.title.slice(0, 1)}</strong></div><div className="taste-copy"><span className="match">{recommendation.score}% <em>match for you</em></span><h3>{item.title}</h3><p>{item.genres || "Personal recommendation"}</p><small>{recommendation.reasons?.[0] || "Selected from your taste profile."}</small></div></article>; }
function DiscoveryCard({ result }: { result: DiscoveryResult }) {
  const item = result.item; const isSeries = item.media_type === "tv" || item.media_type === "anime";
  return <article className="discovery-card"><div className="discovery-poster"><span>{mediaLabel(item.media_type)}</span><strong>{item.title.slice(0, 1)}</strong><b>{result.score}% match</b></div><div className="discovery-card-body"><div className="card-title-row"><div><h3>{item.title}</h3><p>{item.release_year || "—"} · {item.genres || mediaLabel(item.media_type)}</p></div>{item.imdb_rating ? <strong className="imdb">IMDb {item.imdb_rating}</strong> : null}</div><p className="card-description">{item.description || "Selected from Manu AI's discovery catalogue."}</p><div className="meta-pills">{item.runtime && <span>⏱ {item.runtime}</span>}{item.intensity && <span>⚡ {item.intensity}</span>}{item.ending_type && <span>◈ {item.ending_type}</span>}{item.ott_india && <span>▣ {item.ott_india}</span>}{isSeries && item.seasons ? <span>▤ {item.seasons} seasons</span> : null}{isSeries && item.episodes ? <span>• {item.episodes} episodes</span> : null}{isSeries && item.episode_duration ? <span>⌛ {item.episode_duration}</span> : null}{item.media_type === "game" && item.player_modes ? <span>◉ {item.player_modes}</span> : null}{item.media_type === "game" && item.difficulty ? <span>◆ {item.difficulty}</span> : null}{item.media_type === "book" && item.author ? <span>✎ {item.author}</span> : null}{item.media_type === "book" && item.reading_length ? <span>⌛ {item.reading_length}</span> : null}</div><p className="fit-reason">✦ {result.reasons?.[0] || "Matches your saved taste profile."}</p></div></article>;
}
function WebCard({ result }: { result: SearchResult }) { let host = result.url; try { host = new URL(result.url).hostname; } catch {} return <a className="search-result-card" href={result.url} target="_blank" rel="noreferrer"><small>{host}</small><h3>{result.title}</h3><p>{result.snippet || "Open this result."}</p></a>; }
