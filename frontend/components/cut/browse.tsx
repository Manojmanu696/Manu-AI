"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { cardRating, cutPath, mediaTypes, messageFrom, sameTitle, splitLabels, statuses, titleApi, titleTime, type BrowseData, type CutTitle, type ScreenType } from "@/lib/cut";
import { Artwork, CutFrame, Glyph, Poster, Shelf, StatePanel } from "./ui";

const viewTypes: Record<string, ScreenType> = { movies: "movie", tv: "tv", anime: "anime" };
const viewNames: Record<string, string> = { discover: "Discover", movies: "Movies", tv: "TV Series", anime: "Anime", library: "My Library", reviews: "Recently Reviewed" };

function Featured({ titles, saving, save }: { titles: CutTitle[]; saving: string; save: (title: CutTitle) => void }) {
  const [index, setIndex] = useState(0);
  const [pinned, setPinned] = useState<CutTitle[]>();
  const picks = pinned?.map(pick => titles.find(title => sameTitle(title, pick)) ?? pick) ?? titles.slice(0, 3);
  const title = picks[index] ?? picks[0];
  if (!title) return <div className="cut-container cut-empty-home"><StatePanel title="Welcome to Manu’s Cut"><p>Add a title to start your viewing journal.</p><Link className="cut-btn cut-primary" href="/browse/library">Open My Library <Glyph name="arrow"/></Link></StatePanel></div>;

  const saved = !!title.media_id && title.status !== "recommended";
  const pending = saving === cutPath(title);
  const genre = splitLabels(title.genres)[0];
  const metadata = [title.release_year, titleTime(title), genre || mediaTypes[title.media_type]].filter(Boolean);

  return <section className="cut-container cut-hero" aria-label="Featured titles">
    <div className="cut-hero-visual">
      <Artwork title={title} backdrop eager sizes="(max-width: 1600px) 100vw, 1600px"/>
    </div>
    <div className="cut-hero-copy" aria-live="polite">
      <h1>{title.title}</h1>
      <p className="cut-hero-facts">{metadata.join(" · ")}</p>
      {title.description && <p className="cut-feature-summary">{title.description}</p>}
      <div className="cut-actions cut-feature-actions">
        <Link href={cutPath(title)} className="cut-btn cut-feature-open">{title.media_type === "movie" ? "View film" : "View title"} <Glyph name="arrow" size={17}/></Link>
        {saved
          ? <Link className="cut-feature-save" href={cutPath(title)}><Glyph name="check" size={18}/> In My Library</Link>
          : <button className="cut-feature-save" type="button" disabled={pending} onClick={() => {
              setPinned(picks);
              save(title);
            }}><Glyph name="bookmark" size={18}/> {pending ? "Saving…" : "Save to watchlist"}</button>}
      </div>
    </div>
    {picks.length > 1 && <div className="cut-feature-select" role="group" aria-label="Choose a featured title">
      {picks.map((pick, position) => <button key={position} type="button" onClick={() => setIndex(position)} aria-pressed={pick === title}>
        <span>{pick.title}</span>
      </button>)}
    </div>}
  </section>;
}

function HomeContent({ data, saving, save, load }: { data: BrowseData; saving: string; save: (title: CutTitle) => void; load: () => Promise<void> }) {
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoError, setDemoError] = useState("");
  const watching = data.library.filter(title => title.status === "current");
  const watchlist = data.library.filter(title => title.status === "want" || title.status === "on_hold");
  const recommendations = [...data.catalogue, ...data.library.filter(title => title.status === "recommended")];
  const combined = [...recommendations, ...data.library.filter(title => title.status !== "recommended")];
  const filmFeatures = combined.filter(title => title.media_type === "movie" && title.backdrop_url);
  const featured = filmFeatures.length ? filmFeatures : combined;

  async function loadDemo() {
    setDemoBusy(true);
    setDemoError("");
    try {
      await api("/demo/load", { method: "POST" });
      await load();
    } catch (error) {
      setDemoError(messageFrom(error));
    } finally {
      setDemoBusy(false);
    }
  }

  return <>
    <Featured titles={featured} saving={saving} save={save}/>
    <div className="cut-container cut-home-shelves">
      <Shelf name="Recommended for You" href="/browse/discover?status=recommended" titles={recommendations.slice(0, 12)} saving={saving} onSave={save}/>
      <Shelf name="Continue Watching" href="/browse/library?status=current" titles={watching} saving={saving} onSave={save}/>
      <Shelf name="Your Watchlist" href="/browse/library?status=watchlist" titles={watchlist} saving={saving} onSave={save}/>
      <Shelf name="Recently Reviewed" href="/browse/reviews" titles={data.reviewed} saving={saving} onSave={save}/>
      <Shelf name="Movies" href="/browse/movies" titles={combined.filter(title => title.media_type === "movie").slice(0, 12)} saving={saving} onSave={save}/>
      <Shelf name="TV Series" href="/browse/tv" titles={combined.filter(title => title.media_type === "tv").slice(0, 12)} saving={saving} onSave={save}/>
      <Shelf name="Anime" href="/browse/anime" titles={combined.filter(title => title.media_type === "anime").slice(0, 12)} saving={saving} onSave={save}/>
      {!data.library.length && <StatePanel title="Start your viewing journal">
        <p>Save a title to build your watchlist, or load sample records to try the journal.</p>
        <button className="cut-btn cut-secondary" onClick={loadDemo} disabled={demoBusy}>{demoBusy ? "Loading…" : "Load sample library"}</button>
        {demoError && <p role="alert">{demoError}</p>}
      </StatePanel>}
    </div>
  </>;
}

function AddTitle({ onDone }: { onDone: (title: CutTitle) => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const fields = new FormData(event.currentTarget);
    try {
      const title = String(fields.get("title")).trim();
      if (!title) throw new Error("Enter a title.");
      const item = await api<CutTitle>("/cinema/media", { method: "POST", body: JSON.stringify({
        title, media_type: fields.get("type"), release_year: fields.get("year") ? Number(fields.get("year")) : null,
      }) });
      onDone({ ...item, source: "media" });
    } catch (failure) {
      setError(messageFrom(failure));
    } finally {
      setBusy(false);
    }
  }
  if (!open) return <button className="cut-btn cut-secondary" onClick={() => setOpen(true)}><Glyph name="plus"/> Add a title</button>;
  return <form className="cut-form cut-add" onSubmit={add}>
    <label>Title<input name="title" required maxLength={300}/></label>
    <label>Media type<select name="type" aria-label="Media type">{Object.entries(mediaTypes).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
    <label>Year <small>(optional)</small><input name="year" type="number" min="1800" max="2100"/></label>
    <div className="cut-actions"><button className="cut-btn cut-primary" disabled={busy}>Save title</button><button type="button" className="cut-btn cut-secondary" disabled={busy} onClick={() => setOpen(false)}>Cancel</button></div>
    {error && <p role="alert">{error}</p>}
  </form>;
}

function Results({ data, view, saving, save }: { data: BrowseData; view: string; saving: string; save: (title: CutTitle) => void }) {
  const params = useSearchParams();
  const router = useRouter();
  const initialQuery = params.get("q") || "";
  const selectedStatus = params.get("status") || "";
  const [query, setQuery] = useState(initialQuery);
  const [type, setType] = useState("");
  const [genre, setGenre] = useState("");
  const [year, setYear] = useState("");
  const [rating, setRating] = useState("");
  const [status, setStatus] = useState(selectedStatus);
  const [publicState, setPublicState] = useState<{ key: string; items: CutTitle[]; error?: string }>();
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { setQuery(initialQuery); }, [initialQuery]);
  useEffect(() => { setStatus(selectedStatus); }, [selectedStatus]);

  const viewType = viewTypes[view];
  const mediaType = viewType || type;
  const isLibrary = view === "library";
  const isReviews = view === "reviews";
  const canSearchPublic = data.public_search && !isLibrary && !isReviews && query.trim().length >= 2;
  const publicKey = `${mediaType || "all"}:${query.trim()}`;
  useEffect(() => {
    if (!canSearchPublic) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      const encoded = new URLSearchParams({ query: query.trim(), media_type: mediaType });
      api<CutTitle[]>(`/cinema/search?${encoded}`, { signal: controller.signal })
        .then(items => setPublicState({ key: publicKey, items }))
        .catch(error => { if (!controller.signal.aborted) setPublicState({ key: publicKey, items: [], error: messageFrom(error) }); });
    }, 330);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [canSearchPublic, mediaType, publicKey, query, attempt]);

  const local = isReviews ? data.reviewed : isLibrary ? data.library : [...data.library, ...data.catalogue];
  const publicTitles = canSearchPublic && publicState?.key === publicKey && !publicState.error
    ? publicState.items.filter((title, index, all) => !local.some(own => sameTitle(own, title)) && all.findIndex(other => sameTitle(other, title)) === index)
    : [];
  const entries = [...local, ...publicTitles].filter(title => !mediaType || title.media_type === mediaType);
  const genres = [...new Set(entries.flatMap(title => splitLabels(title.genres)))].sort();
  const years = [...new Set(entries.flatMap(title => title.release_year ? [title.release_year] : []))].sort((a, b) => b - a);
  const results = entries.filter(title =>
    (!query.trim() || title.title.toLowerCase().includes(query.trim().toLowerCase()) || publicTitles.includes(title)) &&
    (!genre || splitLabels(title.genres).includes(genre)) &&
    (!year || title.release_year === Number(year)) &&
    (!rating || (cardRating(title)?.value ?? -1) >= Number(rating)) &&
    (!status || (status === "watchlist" ? title.status === "want" || title.status === "on_hold" : (title.status || "recommended") === status)),
  );
  const pendingPublic = canSearchPublic && publicState?.key !== publicKey;
  const publicError = canSearchPublic && publicState?.key === publicKey ? publicState.error : "";
  const canReset = !!(query || type || genre || year || status || rating);

  return <div className="cut-container cut-browse">
    <div className="cut-page-heading">
      <div><h1>{viewNames[view]}</h1><p>{isReviews ? "The final word on what you’ve watched." : isLibrary ? "Your watchlist, viewing progress and reviews." : "Explore your library and discover what to watch next."}</p></div>
      {isLibrary && <AddTitle onDone={title => router.push(cutPath(title))}/>}
    </div>
    <form className="cut-filter" role="search" aria-label="Filter titles" onSubmit={event => event.preventDefault()}>
      <label className="cut-filter-search"><span>Search titles</span><span className="cut-input-icon"><Glyph name="search"/><input id="title-search" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by title" maxLength={200}/></span></label>
      {!viewType && <label>Media type<select aria-label="Media type" value={type} onChange={event => { setType(event.target.value); setGenre(""); setYear(""); }}><option value="">All types</option>{Object.entries(mediaTypes).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>}
      <label>Genre<select aria-label="Genre" value={genre} onChange={event => setGenre(event.target.value)}><option value="">All genres</option>{[...new Set([...genres, ...(genre ? [genre] : [])])].map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Year<select aria-label="Year" value={year} onChange={event => setYear(event.target.value)}><option value="">All years</option>{[...new Set([...years, ...(year ? [Number(year)] : [])])].map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Rating<select aria-label="Rating" value={rating} onChange={event => setRating(event.target.value)}><option value="">Any rating</option>{[9,8,7,6,5].map(value => <option key={value} value={value}>{value}+ / 10</option>)}</select></label>
      <label>Status<select aria-label="Status" value={status} onChange={event => setStatus(event.target.value)}><option value="">Any status</option><option value="watchlist">Watchlist</option>{Object.entries(statuses).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
    </form>
    <div className="cut-results-head"><p role="status">{results.length} {results.length === 1 ? "title" : "titles"}{pendingPublic && " · Searching TMDB…"}</p>
      {canReset && <button className="cut-text-button" onClick={() => { setQuery(""); setGenre(""); setYear(""); setType(""); setRating(""); setStatus(""); if (initialQuery || selectedStatus) router.replace(`/browse/${view}`, { scroll: false }); }}>Clear filters</button>}
    </div>
    {publicError && <div className="cut-inline-notice" role="alert">{publicError} <button className="cut-text-button" onClick={() => { setPublicState(undefined); setAttempt(value => value + 1); }}>Retry</button></div>}
    {results.length ? <div className="cut-grid">{results.map(title => <Poster key={cutPath(title)} title={title} pending={saving === cutPath(title)} onSave={save}/>)}</div>
      : !pendingPublic && <StatePanel title={canReset ? "No matching titles" : isReviews ? "No final reviews yet" : isLibrary ? "Your library is empty" : "No titles available"}>
        <p>{canReset ? "Try a different search or clear a filter." : isReviews ? "Open a title and write your first review." : "Find a title in Discover or add it to your library."}</p>
        {(isLibrary || isReviews) && <Link href="/browse/discover" className="cut-btn cut-secondary">Go to Discover <Glyph name="arrow"/></Link>}
      </StatePanel>}
    {!isLibrary && !isReviews && !data.public_search && <p className="cut-source-note">Searching your library and local catalogue. Public title search requires a TMDB API key.</p>}
  </div>;
}

export function CutBrowse({ view }: { view: string }) {
  const [data, setData] = useState<BrowseData>();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ text: string; error?: boolean }>();
  const [saving, setSaving] = useState("");
  const savingRef = useRef(false);

  async function load(signal?: AbortSignal) {
    setError("");
    try {
      setData(await api<BrowseData>("/cinema/browse", { signal }));
    } catch (failure) {
      if (!signal?.aborted) setError(messageFrom(failure));
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, []);

  async function save(title: CutTitle) {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(cutPath(title));
    setNotice(undefined);
    try {
      const item = await api<CutTitle>(`${titleApi(title)}/status`, { method: "PUT", body: JSON.stringify({ status: "want" }) });
      setData(current => current && ({
        ...current, library: [{ ...title, ...item }, ...current.library.filter(other => other.id !== item.id)],
        catalogue: current.catalogue.filter(other => !sameTitle(other, title)),
      }));
      setNotice({ text: `${title.title} added to your watchlist.` });
    } catch (failure) {
      setNotice({ text: messageFrom(failure), error: true });
    } finally {
      savingRef.current = false;
      setSaving("");
    }
  }

  return <CutFrame>
    {notice && <div className={`cut-toast ${notice.error ? "is-error" : ""}`} role={notice.error ? "alert" : "status"}>{notice.text}<button aria-label="Dismiss message" onClick={() => setNotice(undefined)}><Glyph name="close" size={17}/></button></div>}
    {error ? <div className="cut-container cut-body-spacing"><StatePanel error title="Couldn’t open your catalogue"><p>{error}</p><button className="cut-btn cut-secondary" onClick={() => void load()}>Retry</button></StatePanel></div>
      : !data ? <div className="cut-container cut-body-spacing" role="status" aria-busy="true"><div className="cut-loading"/><p>Opening your catalogue…</p></div>
      : view === "home" ? <HomeContent data={data} save={save} saving={saving} load={load}/>
      : <Results key={view} data={data} view={view} saving={saving} save={save}/>}
  </CutFrame>;
}
