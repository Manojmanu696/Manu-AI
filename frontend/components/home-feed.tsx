"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { API_URL } from "@/lib/api";
import "./home-feed.css";

type Catalogue = {
  id: number; media_type: string; title: string; description?: string; genres?: string; release_year?: number | null;
  image_url?: string; backdrop_url?: string; public_rating?: number | null; imdb_rating?: number | null;
  vote_count?: number; runtime?: string; runtime_minutes?: number | null; episodes?: number | null; seasons?: number | null;
  episode_duration?: string; original_language?: string; series_status?: string; source_provider?: string;
  source_url?: string; watch_url?: string; watch_providers_json?: string; credits_json?: string; trailer_url?: string;
  ott_india?: string; external_id?: string; countries_json?: string;
  is_local?: boolean;
};
type Recommendation = { item: Catalogue; score?: number; fit?: string; reasons: string[]; source?: string; is_local?: boolean };
type Section = { items: Recommendation[]; provider?: string; fetched_at?: string | null; stale?: boolean; error?: string; based_on?: string | null };
type HomeResponse = { sections: Record<string, Section>; refreshing: boolean; last_updated: string | null; stale: boolean;
  providers: Record<string, { status: string; last_error?: string }>; attribution: Record<string, string> };
type SearchFilters = {genre:string;yearFrom:string;yearTo:string;runtimeMax:string;ratingMin:string;language:string;country:string;status:string;seasonsMax:string;episodesMax:string;episodeMinutesMax:string;provider:string};
const emptyFilters:SearchFilters={genre:"",yearFrom:"",yearTo:"",runtimeMax:"",ratingMin:"",language:"",country:"",status:"",seasonsMax:"",episodesMax:"",episodeMinutesMax:"",provider:""};
const ThreeCinema = dynamic(() => import("./three-cinema"), { ssr: false, loading: () => <div className="three-cinema-fallback" aria-hidden="true"/> });

const sectionMeta: Record<string, { title: string; eyebrow?: string }> = {
  continue_watching: { title: "Continue watching" }, personalized_movies: { title: "Picked for your taste", eyebrow: "FILMS" },
  personalized_tv: { title: "Series you may love", eyebrow: "TELEVISION" }, trending_movies: { title: "Trending films" },
  trending_tv: { title: "Trending series" }, hidden_gems: { title: "Underseen, worth finding", eyebrow: "HIDDEN GEMS" },
  psychological_thrillers: { title: "Psychological thrillers" }, mind_games: { title: "Mind games & mysteries" },
  intelligent_stories: { title: "For curious minds" }, now_playing: { title: "In cinemas now" },
  upcoming_movies: { title: "Coming soon" }, recent_releases: { title: "Recently released" },
  top_rated_movies: { title: "Highest rated films" }, top_rated_tv: { title: "Highest rated series" },
  short_movies: { title: "Short films, full stories" }, short_completed_series: { title: "Short & complete series" },
  popular_anime: { title: "Anime worth your time" }, seasonal_anime: { title: "This season in anime" },
  because_you_liked: { title: "Because you liked" },
};
const modes = [
  ["best_fit", "Best fit"], ["psychological", "Psychological"], ["mystery", "Smart mysteries"],
  ["fast_hook", "Fast hook"], ["hidden_gems", "Hidden gems"], ["short_movies", "Short films"],
  ["short_series", "Short series"], ["critically_acclaimed", "Acclaimed, for you"], ["explore", "Explore"], ["surprise", "Surprise me"],
];
const moods = [["", "Any mood"], ["two hours", "I have two hours"], ["clever mystery", "Clever mystery"], ["dark", "Something dark"],
  ["short series", "A short series"], ["English originals", "English originals"], ["entertaining", "Light & entertaining"]];

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Request failed (${res.status})`);
  return res.status === 204 ? undefined as T : res.json();
}

export default function HomeFeed() {
  const [data, setData] = useState<HomeResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [mode, setMode] = useState("best_fit");
  const [mood, setMood] = useState("");
  const [query, setQuery] = useState("");
  const [type, setType] = useState("movie");
  const [filters, setFilters] = useState<SearchFilters>(emptyFilters);
  const [searchResults, setSearchResults] = useState<Recommendation[]>([]);
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({ mode, mood });
      const result = await request<HomeResponse>(`/home?${params}`);
      setData(result); setError(""); setRefreshing(result.refreshing);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load your discovery feed"); }
    finally { setLoading(false); }
  }, [mode, mood]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!refreshing) return;
    const timer = window.setInterval(() => { void load(); }, 2500);
    return () => window.clearInterval(timer);
  }, [refreshing, load]);
  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) { setSearchResults([]); setSearchError(""); setSearching(false); return; }
    const timer = window.setTimeout(async () => {
      setSearching(true); setSearchError("");
      try {
        const types = type === "all" ? ["movie", "tv", "anime"] : [type];
        const resultSets = await Promise.all(types.map(async media => request<Recommendation[]>(`/discover?media_type=${media}&limit=40&query=${encodeURIComponent(term)}`)));
        const merged = resultSets.flat().filter(x => x.item?.title);
        const unique = new Map(merged.map(x => [`${x.item.media_type}:${x.item.external_id || x.item.title}`, x]));
        setSearchResults([...unique.values()]);
      } catch (e) { setSearchError(e instanceof Error ? e.message : "Search could not reach the catalogue"); }
      finally { setSearching(false); }
    }, 350);
    return () => window.clearTimeout(timer);
  }, [query, type]);

  async function refresh() {
    setRefreshing(true); setToast("Refreshing your catalogue…");
    try { await request("/home/refresh", { method: "POST" }); void load(); }
    catch (e) { setToast(e instanceof Error ? e.message : "Refresh could not start"); }
    window.setTimeout(() => setToast(""), 3000);
  }
  async function feedback(item: Catalogue, action: string) {
    try {
      const result = await request<{ feedback_id: number }>(`/discover/${item.id}/feedback`, {
        method: "POST", body: JSON.stringify({ action, context: `${mode}:${mood||"any"}` }),
      });
      setLastFeedbackId(result.feedback_id);
      setToast(action === "watchlist" ? `Saved ${item.title} to your watchlist` : `Saved your feedback for ${item.title}`);
      window.setTimeout(() => setToast(""), 5000);
      void load();
    } catch (e) { setToast(e instanceof Error ? e.message : "Could not save feedback"); }
  }
  async function undoLast() {
    // An undo id is attached by the API response below in `lastFeedbackId`.
    if (lastFeedbackId == null) return;
    try { await request(`/feedback/${lastFeedbackId}/undo`, { method: "POST" }); setToast("Feedback undone"); void load(); }
    catch (e) { setToast(e instanceof Error ? e.message : "Could not undo feedback"); }
    setLastFeedbackId(null);
  }

  const [lastFeedbackId, setLastFeedbackId] = useState<number | null>(null);
  const frontPick = useMemo(() => data?.sections.personalized_movies?.items?.[0] || data?.sections.trending_movies?.items?.[0] || data?.sections.personalized_tv?.items?.[0] || data?.sections.popular_anime?.items?.[0] || data?.sections.tvmaze_catalogue?.items?.[0], [data]);
  const labels = data?.providers || {};
  const hasSearch = query.trim().length >= 2;
  const filtersActive=Object.values(filters).some(Boolean);
  const filteredSearchResults=useMemo(()=>searchResults.filter(({item})=>{
    const genres=(item.genres||"").toLocaleLowerCase();
    const year=item.release_year||0;
    const runtime=item.runtime_minutes||Number.parseInt(item.runtime||"",10)||0;
    const rating=item.public_rating??0;
    const episodeMinutes=Number.parseInt(item.episode_duration||item.runtime||"",10)||0;
    let countries:string[]=[],providers:{name:string}[]=[];
    try{countries=JSON.parse(item.countries_json||"[]")}catch{countries=[]}
    try{providers=JSON.parse(item.watch_providers_json||"[]")}catch{providers=[]}
    return (!filters.genre||genres.includes(filters.genre.toLocaleLowerCase()))
      &&(!filters.yearFrom||year>=Number(filters.yearFrom))&&(!filters.yearTo||year<=Number(filters.yearTo))
      &&(!filters.runtimeMax||!runtime||runtime<=Number(filters.runtimeMax))
      &&(!filters.ratingMin||rating>=Number(filters.ratingMin))
      &&(!filters.language||(item.original_language||"").toLocaleLowerCase().includes(filters.language.toLocaleLowerCase()))
      &&(!filters.country||countries.some(value=>value.toLocaleLowerCase().includes(filters.country.toLocaleLowerCase())))
      &&(!filters.status||(item.series_status||"").toLocaleLowerCase().includes(filters.status.toLocaleLowerCase()))
      &&(!filters.seasonsMax||item.seasons!=null&&item.seasons<=Number(filters.seasonsMax))
      &&(!filters.episodesMax||item.episodes!=null&&item.episodes<=Number(filters.episodesMax))
      &&(!filters.episodeMinutesMax||!episodeMinutes||episodeMinutes<=Number(filters.episodeMinutesMax))
      &&(!filters.provider||providers.some(value=>value.name.toLocaleLowerCase().includes(filters.provider.toLocaleLowerCase()))||(item.ott_india||"").toLocaleLowerCase().includes(filters.provider.toLocaleLowerCase()));
  }),[searchResults,filters]);
  const visibleSections = Object.entries(sectionMeta).filter(([key]) => {
    if (key === "because_you_liked" && !data?.sections[key]?.based_on) return false;
    return (data?.sections[key]?.items?.length || 0) > 0;
  });

  return <main className="feed-page">
    <header className="feed-header">
      <div><p className="feed-overline">MANU AI <span>·</span> PERSONAL CINEMA</p><h1>Your next watch.</h1></div>
      <div className="feed-header-tools"><span className={`freshness ${data?.stale ? "is-stale" : ""}`}><i/>{refreshing ? "Refreshing in background" : data?.stale ? `Some sources need attention${data.last_updated?` · updated ${formatDate(data.last_updated)}`:""}` : data?.last_updated ? `Updated ${formatDate(data.last_updated)}` : "Ready to discover"}</span>
        <button className="quiet-button" onClick={refresh} disabled={refreshing} aria-label="Refresh discovery feed">{refreshing ? "Refreshing…" : "Refresh"}</button>
      </div>
    </header>

    {error && <div className="feed-notice error-notice" role="alert"><div><strong>Discovery is unavailable.</strong><p>{error}</p></div><button onClick={() => { setLoading(true); void load(); }}>Retry</button></div>}
    {data?.stale && <div className="feed-notice stale-notice" role="status"><strong>Some catalogue sections are stale.</strong><span>{refreshing?" Manu is refreshing them in the background.":" Available cached titles remain visible; retry after checking provider setup."}</span></div>}
    {labels.tmdb?.status === "not_configured" && <div className="feed-notice setup-notice"><div><strong>Connect TMDB for films and series.</strong><span> Anime and TVmaze titles can still appear. Add a free TMDB API key to enable movies, TV discovery, trailers and India availability.</span></div><a href="https://developer.themoviedb.org/docs/getting-started" target="_blank" rel="noreferrer">Get a TMDB key ↗</a></div>}

    <section className="feed-controls" aria-label="Recommendation controls">
      <label><span>Mode</span><select value={mode} onChange={e => setMode(e.target.value)}>{modes.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
      <label><span>Right now</span><select value={mood} onChange={e => setMood(e.target.value)}>{moods.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
      {mood && <button className="clear-mood" onClick={() => setMood("")}>Clear mood</button>}
    </section>

    <section className="feed-search" aria-label="Search films and series">
      <span className="feed-search-icon" aria-hidden="true">⌕</span>
      <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search films, series and anime" aria-label="Search films, series and anime" />
      <select value={type} onChange={e => setType(e.target.value)} aria-label="Filter by title type"><option value="movie">Films</option><option value="tv">Series</option><option value="anime">Anime</option><option value="all">Everything</option></select>
      {query && <button className="search-clear" aria-label="Clear search" onClick={() => setQuery("")}>×</button>}
    </section>

    {hasSearch&&<details className="search-filter-panel"><summary>Refine search results{filtersActive&&<span>Filters applied</span>}</summary><div className="search-filter-grid">
      <label>Genre<input value={filters.genre} onChange={e=>setFilters({...filters,genre:e.target.value})} placeholder="e.g. mystery"/></label>
      <label>Release year from<input type="number" min="1900" max="2100" value={filters.yearFrom} onChange={e=>setFilters({...filters,yearFrom:e.target.value})}/></label>
      <label>Release year to<input type="number" min="1900" max="2100" value={filters.yearTo} onChange={e=>setFilters({...filters,yearTo:e.target.value})}/></label>
      <label>Maximum runtime (minutes)<input type="number" min="1" max="600" value={filters.runtimeMax} onChange={e=>setFilters({...filters,runtimeMax:e.target.value})}/></label>
      <label>Minimum public rating<select value={filters.ratingMin} onChange={e=>setFilters({...filters,ratingMin:e.target.value})}><option value="">Any</option>{[5,6,7,8,9].map(x=><option key={x} value={x}>{x}+</option>)}</select></label>
      <label>Original language<input value={filters.language} onChange={e=>setFilters({...filters,language:e.target.value})} placeholder="e.g. en, ja"/></label>
      <label>Country code<input value={filters.country} onChange={e=>setFilters({...filters,country:e.target.value})} placeholder="e.g. IN, US"/></label>
      <label>Series status<input value={filters.status} onChange={e=>setFilters({...filters,status:e.target.value})} placeholder="e.g. Ended"/></label>
      <label>Maximum seasons<input type="number" min="1" max="100" value={filters.seasonsMax} onChange={e=>setFilters({...filters,seasonsMax:e.target.value})}/></label>
      <label>Maximum episodes<input type="number" min="1" max="1000" value={filters.episodesMax} onChange={e=>setFilters({...filters,episodesMax:e.target.value})}/></label>
      <label>Episode length up to (minutes)<input type="number" min="1" max="300" value={filters.episodeMinutesMax} onChange={e=>setFilters({...filters,episodeMinutesMax:e.target.value})}/></label>
      <label>Streaming provider<input value={filters.provider} onChange={e=>setFilters({...filters,provider:e.target.value})} placeholder="Only if current data exists"/></label>
      {filtersActive&&<button className="clear-search-filters" onClick={()=>setFilters(emptyFilters)}>Clear all filters</button>}
    </div></details>}

    {hasSearch ? <section className="feed-search-results"><div className="feed-section-heading"><div><span>CATALOGUE SEARCH</span><h2>Results for “{query.trim()}”</h2></div><small>{searching ? "Searching…" : `${filteredSearchResults.length} titles`}</small></div>
      {searchError && <div className="feed-notice error-notice">{searchError}<button onClick={() => setQuery(query + " ")}>Retry</button></div>}
      {searching && !searchResults.length ? <SkeletonRow/> : filteredSearchResults.length ? <PosterRail items={filteredSearchResults} onFeedback={feedback}/> : !searching && <p className="empty-feed">{searchResults.length?"No titles match these filters. Try broadening them.":"No titles found. Try a broader title, or check provider setup."}</p>}
    </section> : <>
      {!frontPick && loading && <><div className="feed-feature-skeleton"/><SkeletonSection/><SkeletonSection/></>}
      {frontPick && <FeaturePick result={frontPick} onFeedback={feedback}/>}
      {visibleSections.map(([key, meta]) => <FeedSection key={key} title={key === "because_you_liked" && data?.sections[key]?.based_on ? `Because you liked ${data.sections[key].based_on}` : meta.title}
        eyebrow={meta.eyebrow} section={data?.sections[key]} onFeedback={feedback}/>) }
      {!loading && !refreshing && !visibleSections.length && !error && <div className="feed-empty"><h2>Your catalogue is warming up.</h2><p>Manu is checking its public catalogue. Give it a moment, then refresh if nothing appears.</p><button onClick={refresh}>Try again</button></div>}
    </>}

    <footer className="feed-attribution">
      <div className="feed-attribution-main">{data?.attribution?.tmdb && <a href="https://www.themoviedb.org" target="_blank" rel="noreferrer" aria-label="Visit TMDB"><img src="https://www.themoviedb.org/assets/v4/logos/v2/blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg" alt="TMDB" width="92" height="18"/></a>}<span>{data?.attribution?.tmdb || "Movie and series metadata provided by their respective sources."}</span></div>
      <div className="feed-attribution-sources"><span>{data?.attribution?.tvmaze || "TV data provided by TVmaze."}</span><a href="https://www.justwatch.com/in" target="_blank" rel="noreferrer">Streaming availability powered by JustWatch via TMDB</a><span>Your private library and preference signals stay on this device.</span></div>
    </footer>
    {toast && <div className="feed-toast" role="status"><span>{toast}</span>{lastFeedbackId && <button onClick={undoLast}>Undo</button>}</div>}
  </main>;
}

function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? "recently" : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }); }

function FeaturePick({ result, onFeedback }: { result: Recommendation; onFeedback: (item: Catalogue, action: string) => void }) {
  const item = result.item;
  return <section className="feature-pick feature-pick-immersive" style={item.backdrop_url ? { backgroundImage: `linear-gradient(90deg, #111216 0%, rgba(17,18,22,.94) 32%, rgba(17,18,22,.42) 76%, rgba(17,18,22,.28)), url("${safeImage(item.backdrop_url)}")` } : undefined}>
    <ThreeCinema title={item.title}/>
    <div className="feature-copy"><p className="feature-label">A PLACE TO START <span>·</span> {result.fit || "For you"}</p><h2>{item.title}</h2><p className="feature-meta">{item.release_year || ""}{item.release_year && item.genres ? " · " : ""}{item.genres || item.media_type}{item.runtime ? ` · ${item.runtime}` : ""}</p>
      <p className="feature-description">{item.description || "A title from the live catalogue, selected for your next watch."}</p><p className="feature-why">{result.reasons?.[0]}</p>
      <div className="feature-actions"><a className="feature-primary" href={`/title/${item.id}`}>Explore title</a><button onClick={() => onFeedback(item, "watchlist")}>Add to watchlist</button></div>
    </div><a href={`/title/${item.id}`} className="feature-poster-link" aria-label={`View ${item.title}`}><Poster item={item} /></a>
  </section>;
}

function FeedSection({ title, eyebrow, section, onFeedback }: { title: string; eyebrow?: string; section?: Section; onFeedback: (item: Catalogue, action: string) => void }) {
  if (!section?.items?.length) return null;
  return <section className="feed-section"><div className="feed-section-heading"><div>{eyebrow && <span>{eyebrow}</span>}<h2>{title}</h2></div><div className="section-source">{section.stale && <small>Saved data</small>}{section.provider && !["personalized", "local"].includes(section.provider) && <small>From {section.provider === "tmdb" ? "TMDB" : section.provider === "anilist" ? "AniList" : "TVmaze"}</small>}</div></div>
        <PosterRail items={section.items} onFeedback={onFeedback}/>
    {section.error && <p className="section-error">Refresh failed: {section.error}</p>}
  </section>;
}

function PosterRail({ items, onFeedback }: { items: Recommendation[]; onFeedback: (item: Catalogue, action: string) => void }) {
  return <div className="poster-rail">{items.map(({ item, fit, reasons, is_local }) => <article className="poster-item" key={`${item.source_provider || item.media_type}:${item.external_id || item.id}`}>
      {is_local ? <div className="poster-open">{posterContent(item, fit)}</div> : <a href={item.id > 0 ? `/title/${item.id}` : undefined} className="poster-open" aria-label={`Open ${item.title}`}>{posterContent(item, fit)}</a>}
      {!is_local && <div className="poster-actions"><button onClick={() => onFeedback(item, "like")} aria-label={`Like ${item.title}`}>Like</button><button onClick={() => onFeedback(item, "watchlist")}>Watchlist</button><button onClick={() => onFeedback(item, "not_interested")} aria-label={`Not interested in ${item.title}`}>Not for me</button></div>}
      {reasons?.[0] && <small className="poster-reason">{reasons[0]}</small>}
    </article>)}</div>;
}

function posterContent(item: Catalogue, fit?: string) { return <><div className="poster-frame"><Poster item={item}/><span className="poster-fit">{fit || "New to you"}</span></div><h3>{item.title}</h3><p>{[item.release_year, item.genres?.split(",")[0]].filter(Boolean).join(" · ") || item.media_type}</p></>; }

function Poster({ item }: { item: Catalogue }) {
  return item.image_url ? <img src={safeImage(item.image_url)} alt={`${item.title} poster`} loading="lazy" referrerPolicy="no-referrer"/> : <span className="poster-fallback">{item.title?.slice(0, 1) || "M"}</span>;
}
function safeImage(url?: string) { return url && /^https:\/\/(image\.tmdb\.org|s4\.anilist\.co|static\.tvmaze\.com)\//.test(url) ? url : ""; }

function SkeletonRow() { return <div className="poster-rail" aria-label="Loading catalogue results">{Array.from({ length: 6 }, (_, i) => <div className="poster-skeleton" key={i}/>)}</div>; }
function SkeletonSection() { return <section className="feed-section"><div className="skeleton-heading"/><SkeletonRow/></section>; }
