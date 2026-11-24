"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { cardRating, cutPath, mediaTypes, messageFrom, sameTitle, splitLabels, statuses, titleApi, watchMinutes, type BrowseData, type CutTitle, type ScreenType } from "@/lib/cut";
import { CutFrame, Glyph, Poster, Shelf, StatePanel } from "./ui";

const viewTypes: Record<string, ScreenType> = { movies: "movie", tv: "tv", anime: "anime" };
const viewNames: Record<string, string> = { discover: "Discover", movies: "Movies", tv: "TV Series", anime: "Anime", library: "My Library", reviews: "Recently Reviewed" };

function HomeContent({ data, saving, save }: { data: BrowseData; saving: string; save: (title: CutTitle) => void }) {
  const combined = [...data.fresh, ...data.library.filter(title => ["want", "on_hold"].includes(title.status || ""))];
  const genreLinks = [...new Set(combined.flatMap(title => splitLabels(title.genres)))].slice(0, 7);

  return <>
    <div className="cut-container cut-home-shelves">
      {genreLinks.length > 0 && <nav className="cut-genre-links" aria-label="Browse by genre">
        {genreLinks.map(genre => <Link key={genre} href={`/browse/discover?genre=${encodeURIComponent(genre)}`}>{genre}</Link>)}
      </nav>}
      <Shelf name="Recently Reviewed" href="/browse/reviews" titles={data.reviewed} saving={saving} onSave={save}/>
      <Shelf name="Movies" href="/browse/movies" titles={combined.filter(title => title.media_type === "movie").slice(0, 12)} saving={saving} onSave={save}/>
      <Shelf name="TV Series" href="/browse/tv" titles={combined.filter(title => title.media_type === "tv").slice(0, 12)} saving={saving} onSave={save}/>
      <Shelf name="Anime" href="/browse/anime" titles={combined.filter(title => title.media_type === "anime").slice(0, 12)} saving={saving} onSave={save}/>
      {!data.library.length && <StatePanel title="Start your viewing journal">
        <p>Save a title to build your watchlist and viewing journal.</p>

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
  const initialGenre = params.get("genre") || "";
  const [genre, setGenre] = useState(initialGenre);
  useEffect(() => { setGenre(initialGenre); }, [initialGenre]);
  const [year, setYear] = useState("");
  const [rating, setRating] = useState("");
  const [status, setStatus] = useState(selectedStatus);
  const [language, setLanguage] = useState("");
  const [duration, setDuration] = useState("");
  const [constrained, setConstrained] = useState<{key: string; items: CutTitle[]}>();
  const [constraintError, setConstraintError] = useState("");
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

  const freshOnly = view === "discover" && !query.trim() && (!status || status === "recommended");
  const verifyConstraints = freshOnly && !!(language || duration);
  const constraintKey = JSON.stringify([mediaType, language, duration]);
  useEffect(() => {
    if (!verifyConstraints) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setConstraintError("");
      const query = new URLSearchParams({ limit: "30" });
      if (mediaType) query.set("media_type", mediaType);
      if (language) query.set("language", language);
      if (duration && Number(duration) > 0) query.set("max_minutes", duration);
      api<{item: CutTitle; source: string; score: number; reasons: string[]; verdict: string; caveat: string; fit_confidence: string}[]>(
        `/discover?${query}`, {signal: controller.signal},
      ).then(rows => {
        if (!controller.signal.aborted) setConstrained({key: constraintKey, items: rows.flatMap(row =>
          row.item.media_type in mediaTypes ? [{
            ...row.item, source: row.source === "public_tmdb" ? row.item.media_type : "catalogue",
            score: row.score, reasons: row.reasons, verdict: row.verdict, caveat: row.caveat, fit_confidence: row.fit_confidence,
          }] : [])});
      }).catch(failure => { if (!controller.signal.aborted) setConstraintError(messageFrom(failure)); });
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [verifyConstraints, mediaType, language, duration, constraintKey]);
  const local = isReviews ? data.reviewed : isLibrary ? data.library : freshOnly ? (verifyConstraints ? constrained?.key === constraintKey ? constrained.items : [] : data.fresh) : [...data.library, ...data.catalogue];
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
    (verifyConstraints || !language || splitLabels(title.language).includes(language) ||
      title.audio_languages?.includes(({English:"en", Japanese:"ja", Hindi:"hi", Malayalam:"ml", Korean:"ko"} as Record<string,string>)[language])) &&
    (verifyConstraints || !duration || (watchMinutes(title) ?? Infinity) <= Number(duration)) &&
    (!rating || (cardRating(title)?.value ?? -1) >= Number(rating)) &&
    (!status || (status === "watchlist" ? title.status === "want" || title.status === "on_hold" : (title.status || "unknown") === status || status === "recommended" && freshOnly)),
  );
  const pendingPublic = canSearchPublic && publicState?.key !== publicKey;
  const pendingConstraints = verifyConstraints && constrained?.key !== constraintKey && !constraintError;
  const publicError = canSearchPublic && publicState?.key === publicKey ? publicState.error : "";
  const canReset = !!(query || type || genre || year || status || rating || language || duration);

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
      <label>Audio language<select value={language} onChange={event => setLanguage(event.target.value)}><option value="">Any verified language</option>{["English", "Japanese", "Hindi", "Malayalam", "Korean"].map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Total minutes<input type="number" min={1} placeholder="Any length" value={duration} onChange={event => setDuration(event.target.value)}/></label>
    </form>
    <div className="cut-results-head"><p role="status">{results.length} {results.length === 1 ? "title" : "titles"}{pendingPublic && " · Searching catalogues…"}{pendingConstraints && " · Checking language and runtime…"}</p>
      {canReset && <button className="cut-text-button" onClick={() => { setQuery(""); setGenre(""); setYear(""); setType(""); setRating(""); setStatus(""); setLanguage(""); setDuration(""); if (initialQuery || initialGenre || selectedStatus) router.replace(`/browse/${view}`, { scroll: false }); }}>Clear filters</button>}
    </div>
    {publicError && <div className="cut-inline-notice" role="alert">{publicError} <button className="cut-text-button" onClick={() => { setPublicState(undefined); setAttempt(value => value + 1); }}>Retry</button></div>}
    {verifyConstraints && constraintError && <p role="alert">{constraintError}</p>}
    {results.length ? <div className="cut-grid">{results.map(title => <Poster key={cutPath(title)} title={title} pending={saving === cutPath(title)} onSave={save}/>)}</div>
      : !pendingPublic && !pendingConstraints && <StatePanel title={canReset ? "No matching titles" : isReviews ? "No final reviews yet" : isLibrary ? "Your library is empty" : "No titles available"}>
        <p>{canReset ? "Try a different search or clear a filter." : isReviews ? "Open a title and write your first review." : "Find a title in Discover or add it to your library."}</p>
        {(isLibrary || isReviews) && <Link href="/browse/discover" className="cut-btn cut-secondary">Go to Discover <Glyph name="arrow"/></Link>}
      </StatePanel>}
    {!isLibrary && !isReviews && !data.public_search && <p className="cut-source-note">Searching your library and local catalogue. Public title search requires a TMDB API key.</p>}
  </div>;
}

export function CutBrowse({ view, embedded = false }: { view: string; embedded?: boolean }) {
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
    const refresh = () => { void load(controller.signal); };
    window.addEventListener("manu-taste-updated", refresh);
    window.addEventListener("manu-library-updated", refresh);
    return () => {
      controller.abort();
      window.removeEventListener("manu-taste-updated", refresh);
      window.removeEventListener("manu-library-updated", refresh);
    };
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
        fresh: current.fresh.filter(other => !sameTitle(other, title)),
      }));
      setNotice({ text: `${title.title} added to your watchlist.` });
    } catch (failure) {
      setNotice({ text: messageFrom(failure), error: true });
    } finally {
      savingRef.current = false;
      setSaving("");
    }
  }

  const content = <>
    {notice && <div className={`cut-toast ${notice.error ? "is-error" : ""}`} role={notice.error ? "alert" : "status"}>{notice.text}<button aria-label="Dismiss message" onClick={() => setNotice(undefined)}><Glyph name="close" size={17}/></button></div>}
    {error ? <div className="cut-container cut-body-spacing"><StatePanel error title="Couldn’t open your catalogue"><p>{error}</p><button className="cut-btn cut-secondary" onClick={() => void load()}>Retry</button></StatePanel></div>
      : !data ? <div className="cut-container cut-body-spacing" role="status" aria-busy="true"><div className="cut-loading"/><p>Opening your catalogue…</p></div>
      : view === "home" ? <HomeContent data={data} save={save} saving={saving}/>
      : <Results key={view} data={data} view={view} saving={saving} save={save}/>}
  </>;

  return embedded ? <section className="cut cut-embedded" aria-label="Catalogue and viewing journal">{content}</section> : <CutFrame>{content}</CutFrame>;
}
