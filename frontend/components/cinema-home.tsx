"use client";

import { useEffect, useRef, useState } from "react";
import { api, MediaItem, Recommendation } from "@/lib/api";
import SearchExperience from "./search-experience";
import "./cinema-home.css";

type Title = Pick<MediaItem, "id" | "title" | "media_type" | "description" | "genres" | "tags" | "runtime" | "release_year" | "image_url"> & {
  imdb_rating?: number | null;
  personal_rating?: number | null;
  ott_india?: string;
  watch_url?: string;
};
type PickEntry = { item: Title; score?: number; reasons?: string[]; source?: string };
const types: Record<string, string> = { movie: "Film", tv: "Series", anime: "Anime", game: "Game", book: "Book" };

function Artwork({ item }: { item?: Title }) {
  const [failed, setFailed] = useState(false);
  return (
    <span className="cinema-art" data-type={item?.media_type}>
      {item?.image_url && !failed && <img src={item.image_url} alt="" onError={() => setFailed(true)} />}
    </span>
  );
}

function Section({ title, entries, onOpen, compact = false }: {
  title: string; entries: PickEntry[]; onOpen: (entry: PickEntry) => void; compact?: boolean;
}) {
  if (!entries.length) return null;
  return (
    <section className="cinema-shelf" aria-label={title}>
      <h2>{title}</h2>
      <div className={compact ? "cinema-grid cinema-grid-compact" : "cinema-grid"}>
        {entries.map(entry => (
          <button key={entry.item.id} className="cinema-tile" onClick={() => onOpen(entry)}>
            <Artwork item={entry.item} />
            <span className="cinema-tile-copy">
              <strong>{entry.item.title}</strong>
              <small>{entry.item.genres || types[entry.item.media_type]}</small>
              {entry.score != null && <span className="cinema-match">{entry.score}% match</span>}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

function TitleDetails({ entry, saved, onClose, onSave }: {
  entry: PickEntry; saved?: MediaItem; onClose: () => void; onSave: () => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { item, score, reasons } = entry;
  useEffect(() => { dialog.current?.showModal(); }, []);

  async function save() {
    setSaving(true);
    setError("");
    try {
      await onSave();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this title.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <dialog className="cinema-dialog" ref={dialog} onClose={onClose} aria-labelledby="cinema-title">
      <Artwork item={item} />
      <div className="cinema-dialog-copy">
        <button type="button" className="cinema-close" onClick={() => dialog.current?.close()} aria-label="Close details">×</button>
        <p className="cinema-kicker">{types[item.media_type]}{item.release_year && ` · ${item.release_year}`}</p>
        <h2 id="cinema-title">{item.title}</h2>
        <p>{[item.genres, item.runtime].filter(Boolean).join(" · ")}</p>
        <p>{item.description}</p>
        {(score != null || item.imdb_rating != null || saved?.personal_rating != null) && (
          <dl className="cinema-facts">
            {score != null && <div><dt>Personal match</dt><dd>{score}%</dd></div>}
            {item.imdb_rating != null && entry.source !== "public_tmdb" && <div><dt>IMDb</dt><dd>{item.imdb_rating}/10</dd></div>}
            {saved?.personal_rating != null && <div><dt>Your rating</dt><dd>{saved.personal_rating}/10</dd></div>}
          </dl>
        )}
        {!!reasons?.length && <p><strong>Why it fits</strong><br />{reasons.join(" · ")}</p>}
        {item.ott_india && <p><strong>Availability in India</strong><br />{item.ott_india}</p>}
        <div className="cinema-actions">
          <button className="cinema-button" disabled={saving || !!saved} onClick={save}>
            {saved ? "In your library" : saving ? "Saving…" : "+ Add to watchlist"}
          </button>
          {item.watch_url?.startsWith("https://") && <a className="cinema-button" href={item.watch_url} target="_blank" rel="noreferrer">Where to watch ↗</a>}
        </div>
        {error && <p role="alert">{error}</p>}
      </div>
    </dialog>
  );
}

export default function CinemaHome({ items, recommendations, onRefresh }: {
  items: MediaItem[]; recommendations: Recommendation[]; onRefresh: () => Promise<void>;
}) {
  const [catalogue, setCatalogue] = useState<PickEntry[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [active, setActive] = useState(0);
  const [detail, setDetail] = useState<PickEntry | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api<PickEntry[]>("/discover?limit=24", { signal: controller.signal })
      .then(entries => { setCatalogue(entries); setStatus("ready"); })
      .catch(() => { if (!controller.signal.aborted) setStatus("error"); });
    return () => controller.abort();
  }, [items]);

  const feed: PickEntry[] = catalogue.length ? catalogue : recommendations;
  const featured = feed.filter(entry => ["movie", "tv", "anime"].includes(entry.item.media_type)).slice(0, 3);
  const slides = featured.length ? featured : feed.slice(0, 3);
  const hero = slides[active % (slides.length || 1)];
  const continueEntries = items.filter(item => item.status === "current").slice(0, 8).map(item => ({ item }));
  const savedEntries = items.filter(item => item.status === "want" || item.status === "on_hold").slice(0, 8).map(item => ({ item }));

  async function saveTitle(item: Title) {
    await api("/media", {
      method: "POST",
      body: JSON.stringify({
        title: item.title, media_type: item.media_type, description: item.description,
        genres: item.genres, tags: item.tags, runtime: item.runtime,
        release_year: item.release_year, image_url: item.image_url, status: "want",
      }),
    });
    await onRefresh();
  }

  return (
    <>
      <SearchExperience browse={
        <>
          <section className="cinema-hero" aria-label="Featured picks">
            <Artwork key={hero?.item.id ?? "welcome"} item={hero?.item} />
            <div className="cinema-hero-copy">
              <p className="cinema-kicker">{hero ? "Tonight’s pick" : "Manu AI · Browse"}</p>
              <h1>{hero?.item.title ?? "Find your next favourite."}</h1>
              {hero && <p className="cinema-hero-meta">
                {hero.item.imdb_rating != null && hero.source !== "public_tmdb" && (
                  <span className="cinema-imdb"><b>IMDb</b> {hero.item.imdb_rating} <span aria-hidden="true">·</span> </span>
                )}
                {[types[hero.item.media_type], hero.item.release_year, hero.item.runtime, hero.score != null && `${hero.score}% match`].filter(Boolean).join(" · ")}
              </p>}
              <p className="cinema-synopsis">{hero?.item.description || (hero ? hero.reasons?.[0] : "Discover films, series, anime, games and books.")}</p>
              <div className="cinema-actions">
                {hero && <button className="cinema-button cinema-primary" onClick={() => setDetail(hero)}>View title <span aria-hidden="true">↗</span></button>}
                <a className="cinema-button" href="/discovery">Explore catalogue</a>
              </div>
            </div>
            {slides.length > 1 && <div className="cinema-carousel" aria-label="Choose a featured title">
              <button className="cinema-step" aria-label="Previous title" onClick={() => setActive((active + slides.length - 1) % slides.length)}>‹</button>
              {slides.map((entry, index) => (
                <button key={entry.item.id} className="cinema-thumb" aria-label={entry.item.title} aria-pressed={entry === hero} onClick={() => setActive(index)}>
                  <Artwork item={entry.item} />
                  <span>{entry.item.title}</span>
                </button>
              ))}
              <button className="cinema-step" aria-label="Next title" onClick={() => setActive((active + 1) % slides.length)}>›</button>
            </div>}
          </section>
          {status === "loading" && <p className="cinema-status" role="status">Loading recommendations…</p>}
          {status === "error" && <p className="cinema-status" role="status">The discovery catalogue is currently unavailable.</p>}
          <Section title="Recommended for you" entries={feed.slice(0, 4)} onOpen={setDetail} compact />
          <Section title="Continue watching, reading or playing" entries={continueEntries} onOpen={setDetail} />
          <Section title="Your watchlist" entries={savedEntries} onOpen={setDetail} />
          {Object.entries(types).map(([type, label]) => (
            <Section key={type} title={type === "anime" ? "Anime" : `${label}s`} entries={feed.filter(entry => entry.item.media_type === type).slice(0, 8)} onOpen={setDetail} />
          ))}
        </>
      } />
      {detail && <TitleDetails entry={detail} saved={items.find(item =>
        item.media_type === detail.item.media_type && item.title.trim().toLowerCase() === detail.item.title.trim().toLowerCase()
      )} onClose={() => setDetail(null)} onSave={() => saveTitle(detail.item)} />}
    </>
  );
}
