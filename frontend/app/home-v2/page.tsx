"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { api, MediaItem } from "@/lib/api";
import { Sidebar } from "@/components/sidebar";
import { Icon } from "@/components/icons";
import styles from "./home-v2.module.css";

type Mode = "ai" | "web";
type Category = "all" | "movies" | "anime" | "tv" | "games" | "books" | "videos" | "websites";
type SearchResult = { title: string; url: string; snippet: string; provider?: string };
type SearchResponse = { query: string; results: SearchResult[]; provider: string };
type ChatResponse = { answer: string; mode: string; facts?: string[]; recommendations?: { title: string; type: string; score: number; reason?: string }[]; sources?: SearchResult[]; assumptions?: string[] };

const categories: { id: Category; label: string; icon: string }[] = [
  { id: "all", label: "All", icon: "search" },
  { id: "movies", label: "Movies", icon: "movie" },
  { id: "anime", label: "Anime", icon: "anime" },
  { id: "tv", label: "TV Shows", icon: "tv" },
  { id: "games", label: "Games", icon: "game" },
  { id: "books", label: "Books", icon: "book" },
  { id: "videos", label: "Videos", icon: "search" },
  { id: "websites", label: "Websites", icon: "search" },
];

export default function HomeV2() {
  const [view, setView] = useState("home");
  const [mode, setMode] = useState<Mode>("ai");
  const [category, setCategory] = useState<Category>("all");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [answer, setAnswer] = useState<ChatResponse | null>(null);
  const [library, setLibrary] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (view === "library") loadLibrary();
  }, [view]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function loadLibrary() {
    try {
      setLibraryLoading(true);
      setLibrary(await api<MediaItem[]>("/media"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load your library");
    } finally {
      setLibraryLoading(false);
    }
  }

  async function runSearch(e?: FormEvent, overrides?: { query?: string; category?: Category; mode?: Mode }) {
    e?.preventDefault();
    const clean = (overrides?.query ?? query).trim();
    const activeCategory = overrides?.category ?? category;
    const activeMode = overrides?.mode ?? mode;
    if (!clean) {
      inputRef.current?.focus();
      return;
    }

    setQuery(clean);
    setCategory(activeCategory);
    setMode(activeMode);
    setLoading(true);
    setError("");
    setView("results");
    setAnswer(null);
    setResults([]);

    try {
      const search = await fetch(`/api/search?q=${encodeURIComponent(clean)}&category=${activeCategory}`, { cache: "no-store" });
      if (!search.ok) throw new Error("Web search failed");
      const web = (await search.json()) as SearchResponse;
      setResults(web.results || []);

      if (activeMode === "ai") {
        const context = (web.results || []).slice(0, 8).map((r, i) => `${i + 1}. ${r.title}\n${r.url}\n${r.snippet}`).join("\n\n");
        const prompt = `User request: ${clean}\nCategory: ${activeCategory}\n\nCurrent public web search results:\n${context}\n\nAnswer the user directly. Use the web results as current evidence when useful. If the request is about entertainment, give concrete suggestions and explain why. Do not claim that the web was not searched.`;
        const ai = await api<ChatResponse>("/chat", { method: "POST", body: JSON.stringify({ message: prompt }) });
        setAnswer(ai);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  function selectCategory(next: Category) {
    setCategory(next);
    if (query.trim()) runSearch(undefined, { category: next });
  }

  function startAI() {
    setMode("ai");
    setView("home");
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function openWeb() {
    setMode("web");
    setView("home");
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  const activeLabel = view === "library" ? "Library" : view === "results" ? "Search" : "Home";

  return (
    <main className={styles.app}>
      <Sidebar
        active={view === "home" || view === "results" ? "home" : "movie"}
        onNavigate={(id) => {
          if (id === "home") setView("home");
          else if (id === "ai") startAI();
          else if (["movie", "anime", "tv", "game", "book"].includes(id)) {
            const mapped = id === "movie" ? "movies" : id === "game" ? "games" : id === "tv" ? "tv" : id === "book" ? "books" : "anime";
            setCategory(mapped as Category);
            setView("library");
          } else setView("home");
        }}
      />

      <section className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.crumb}>Manu AI <span>/</span> {activeLabel}</div>
          <div className={styles.topRight}>
            <button className={styles.topSearch} onClick={() => inputRef.current?.focus()} aria-label="Focus search"><Icon name="search" /></button>
            <div className={styles.avatar}>M</div>
          </div>
        </header>

        <div className={styles.scroll}>
          {view === "library" ? (
            <LibraryView category={category} items={library} loading={libraryLoading} onSearch={(text) => { setQuery(text); setView("home"); requestAnimationFrame(() => inputRef.current?.focus()); }} />
          ) : (
            <div className={styles.home}>
              <section className={styles.hero}>
                <div className={styles.eyebrow}>MANU AI · PERSONAL SEARCH</div>
                <h1>Search the web.<br /><em>Think with your taste.</em></h1>
                <p>One search box for the web, your library, and Manu AI. No redirect. No second textbox.</p>
              </section>

              <section className={styles.searchZone}>
                <div className={styles.modeRow}>
                  <div className={styles.modeSwitch} aria-label="Search mode">
                    <button type="button" className={mode === "ai" ? styles.modeActive : ""} onClick={startAI}><span>✦</span> AI Search</button>
                    <button type="button" className={mode === "web" ? styles.modeActive : ""} onClick={openWeb}><span>⌕</span> Web Search</button>
                  </div>
                  <a className={styles.googleLink} href={query.trim() ? `https://www.google.com/search?q=${encodeURIComponent(query)}` : "https://www.google.com/"} target="_blank" rel="noreferrer">Open Google ↗</a>
                </div>

                <form className={styles.searchBox} onSubmit={(e) => runSearch(e)}>
                  <Icon name="search" size={23} />
                  <input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)} placeholder={mode === "ai" ? "Ask anything — or search for a movie, video, website…" : "Search the web for anything…"} autoComplete="off" />
                  {query && <button type="button" className={styles.clear} onClick={() => { setQuery(""); setResults([]); setAnswer(null); setView("home"); }}>×</button>}
                  <button className={styles.searchButton} disabled={loading}>{loading ? "Searching…" : "Search"}</button>
                </form>

                <div className={styles.categories}>
                  {categories.map((c) => <button type="button" key={c.id} className={category === c.id ? styles.categoryActive : ""} onClick={() => selectCategory(c.id)}><Icon name={c.icon} size={15} /> {c.label}</button>)}
                </div>

                <div className={styles.helperRow}><span>⌘ K to focus</span><span>Live public-web results</span><span>Local taste stays local</span></div>
              </section>

              {error && <div className={styles.error}>{error}</div>}

              {view === "results" && (
                <section className={styles.resultsLayout}>
                  <div className={styles.resultsColumn}>
                    <div className={styles.resultsHead}><div><span>SEARCH RESULTS</span><h2>{query}</h2></div><span>{results.length} results</span></div>
                    {mode === "ai" && answer && <article className={styles.aiCard}>
                      <div className={styles.cardLabel}>MANU AI · {answer.mode || "LOCAL"}</div>
                      <h3>Manu's answer</h3>
                      <p className={styles.answer}>{answer.answer}</p>
                      {answer.recommendations?.length ? <div className={styles.recommendations}><b>Recommended</b><div>{answer.recommendations.slice(0, 6).map((r) => <span key={r.title}>{r.title}</span>)}</div></div> : null}
                    </article>}
                    {results.length ? results.map((r, i) => <SearchResultCard key={`${r.url}-${i}`} result={r} category={category} />) : !loading && <div className={styles.noResults}><h3>No results returned.</h3><p>Try a broader query, switch category, or open Google for a full external search.</p></div>}
                  </div>
                  <aside className={styles.sideColumn}>
                    <div className={styles.sideCard}>
                      <span className={styles.cardLabel}>QUICK ACTIONS</span>
                      <button onClick={() => runSearch(undefined, { mode: "web", category: "videos" })}>Find videos</button>
                      <button onClick={() => runSearch(undefined, { mode: "web", category: "movies" })}>Find movies</button>
                      <button onClick={() => runSearch(undefined, { mode: "web", category: "games" })}>Find games</button>
                      <button onClick={() => runSearch(undefined, { mode: "web", category: "websites" })}>Find websites</button>
                    </div>
                    <div className={styles.sideCard}><span className={styles.cardLabel}>SEARCH MODE</span><p>{mode === "ai" ? "AI mode searches the public web first, then asks Manu AI to interpret the results." : "Web mode gives you direct search results without an AI rewrite."}</p></div>
                  </aside>
                </section>
              )}

              {view === "home" && <HomeSuggestions onSearch={(text, cat) => runSearch(undefined, { query: text, category: cat })} />}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function SearchResultCard({ result, category }: { result: SearchResult; category: Category }) {
  const host = (() => { try { return new URL(result.url).hostname.replace(/^www\./, ""); } catch { return result.provider || "web"; } })();
  const isVideo = category === "videos" || /youtube|youtu\.be|vimeo|dailymotion/i.test(result.url);
  return <a className={styles.resultCard} href={result.url} target="_blank" rel="noreferrer"><div className={styles.resultIcon}>{isVideo ? "▶" : "↗"}</div><div className={styles.resultBody}><div className={styles.resultUrl}>{host}</div><h3>{result.title}</h3><p>{result.snippet || "Open this result to read the full page."}</p></div><span className={styles.resultArrow}>↗</span></a>;
}

function HomeSuggestions({ onSearch }: { onSearch: (q: string, category: Category) => void }) {
  const suggestions = [
    ["Best psychological thriller movies with a crazy ending", "movies"],
    ["Best short anime to watch this week", "anime"],
    ["Best story games like Red Dead Redemption 2", "games"],
    ["Latest AI coding tools worth trying", "websites"],
  ] as [string, Category][];
  return <section className={styles.discovery}><div className={styles.discoveryHead}><div><span>START HERE</span><h2>What do you want to find?</h2></div><p>Pick a category or type anything. Manu will search instead of sending you to another page.</p></div><div className={styles.suggestionGrid}>{suggestions.map(([text, cat]) => <button type="button" key={text} onClick={() => onSearch(text, cat)}><small>{cat.toUpperCase()}</small><strong>{text}</strong><span>Search →</span></button>)}</div></section>;
}

function LibraryView({ category, items, loading, onSearch }: { category: Category; items: MediaItem[]; loading: boolean; onSearch: (q: string) => void }) {
  const localType = category === "movies" ? "movie" : category === "anime" ? "anime" : category === "tv" ? "tv" : category === "games" ? "game" : category === "books" ? "book" : "";
  const visible = localType ? items.filter(i => i.media_type === localType) : items;
  return <div className={styles.libraryPage}><div className={styles.libraryHero}><span>YOUR LIBRARY</span><h1>{category === "all" ? "Everything" : categories.find(c => c.id === category)?.label}</h1><p>{visible.length} saved locally. Search the public web below when your library is empty.</p></div><div className={styles.librarySearch}><Icon name="search"/><input placeholder={`Search ${category === "all" ? "your library" : "your " + category}…`} onChange={e => onSearch(e.target.value)} /></div>{loading ? <div className={styles.noResults}>Loading your local library…</div> : visible.length ? <div className={styles.libraryGrid}>{visible.map(item => <article className={styles.libraryCard} key={item.id}><div className={styles.libraryType}>{item.media_type}</div><h3>{item.title}</h3><p>{item.genres || item.description || "No description yet."}</p>{item.personal_rating ? <b>★ {item.personal_rating}/10</b> : <small>{item.status.replace("_", " ")}</small>}</article>)}</div> : <div className={styles.emptyLibrary}><div>✦</div><h2>No saved {category === "all" ? "items" : category} yet.</h2><p>This is no longer a dead end. Use the search box above to discover current {category === "all" ? "movies, games, books, videos and websites" : category} from the web.</p></div>}</div>;
}
