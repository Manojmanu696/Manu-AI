"use client";

import { useEffect, useRef, useState } from "react";
import { api, MediaItem, Recommendation } from "@/lib/api";
import SearchExperience from "./search-experience";
import Link from "next/link";
import { Poster } from "./cut/ui";
import { CardFacts, useTitleCard } from "./cut/card-facts";
import { cutPath, mediaTypes, type CutTitle } from "@/lib/cut";

type Title = Pick<MediaItem, "id" | "title" | "media_type" | "description" | "genres" | "tags" | "runtime" | "release_year" | "image_url"> & {
  imdb_rating?: number | null;
  personal_rating?: number | null;
  ott_india?: string;
  watch_url?: string;
};
type PickEntry = { item: Title; score?: number; reasons?: string[]; source?: string; verdict?: string; caveat?: string };
const types: Record<string, string> = { movie: "Film", tv: "Series", anime: "Anime", game: "Game", book: "Book" };

function screenTitle(entry: PickEntry): CutTitle | undefined {
  const { item } = entry;
  if (!(item.media_type in mediaTypes)) return;
  const media_type = item.media_type as CutTitle["media_type"];
  const source = entry.source === "public_tmdb" ? media_type : entry.source === "local_catalogue" ? "catalogue" : "media";
  return { ...item, source, media_type, score: entry.score, reasons: entry.reasons, verdict: entry.verdict, caveat: entry.caveat, release_year: item.release_year ?? undefined,
    ...(source === "media" ? { media_id: item.id } : {}) };
}

function FeaturedFacts({ title }: { title: CutTitle }) {
  const card = useTitleCard(title);
  return <section className="cinema-featured-facts cut" ref={card.ref} aria-label={`Watch details for ${title.title}`}>
    <CardFacts {...card}/>
  </section>;
}

function Artwork({ item, featured = false }: { item?: Title; featured?: boolean }) {
  const [failedUrl, setFailedUrl] = useState<string>();
  const imageUrl = item?.image_url;
  const hasImage = !!imageUrl && imageUrl !== failedUrl;
  return (
    <span className={`cinema-art${featured ? " cinema-art-featured" : ""}`} data-type={item?.media_type}>
      {hasImage ? <img src={imageUrl} alt="" loading={featured ? "eager" : "lazy"} onError={() => setFailedUrl(imageUrl)} />
        : !featured && item && <span className="cinema-art-initial" aria-hidden="true">{item.title.trim().charAt(0).toUpperCase()}</span>}
    </span>
  );
}

function Section({ title, entries, onOpen, href }: {
  title: string; entries: PickEntry[]; onOpen: (entry: PickEntry) => void; href?: string;
}) {
  if (!entries.length) return null;
  return (
    <section className="cinema-shelf" aria-label={title}>
      <header className="cinema-shelf-heading">
        <h2>{title}</h2>
        {href && <Link href={href} aria-label={`View all: ${title}`}>View all <span aria-hidden="true">→</span></Link>}
      </header>
      <div className="cinema-grid cut">
        {entries.map(entry => {
          const screen = screenTitle(entry);
          if (screen) return <Poster key={cutPath(screen)} title={screen}/>;
          return (
          <button key={entry.item.id} className="cinema-tile" onClick={() => onOpen(entry)}>
            <Artwork item={entry.item} />
            <span className="cinema-tile-copy">
              <strong>{entry.item.title}</strong>
              <small>{entry.item.genres || types[entry.item.media_type]}</small>
              {entry.score != null && <span className="cinema-match">{entry.score}% match</span>}
            </span>
          </button>
          );
        })}
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
    const refresh = () => api<PickEntry[]>("/discover?limit=24", { signal: controller.signal })
      .then(entries => { setCatalogue(entries); setStatus("ready"); })
      .catch(() => { if (!controller.signal.aborted) setStatus("error"); });
    void refresh();
    window.addEventListener("manu-taste-updated", refresh);
    window.addEventListener("manu-library-updated", refresh);
    return () => {
      controller.abort();
      window.removeEventListener("manu-taste-updated", refresh);
      window.removeEventListener("manu-library-updated", refresh);
    };
  }, [items]);

  const feed: PickEntry[] = catalogue.length ? catalogue : recommendations;
  const featured = feed.filter(entry => ["movie", "tv", "anime"].includes(entry.item.media_type)).slice(0, 3);
  const slides = featured.length ? featured : feed.slice(0, 3);
  const hero = slides[active % (slides.length || 1)];
  const heroScreen = hero && screenTitle(hero);
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
            <Artwork key={hero?.item.id ?? "welcome"} item={hero?.item} featured />
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
                {heroScreen ? <Link href={cutPath(heroScreen)} className="cinema-button cinema-primary">View title <span aria-hidden="true">↗</span></Link>
                  : hero && <button className="cinema-button cinema-primary" onClick={() => setDetail(hero)}>View title <span aria-hidden="true">↗</span></button>}
                <Link className="cinema-button" href="/browse/discover">Explore catalogue</Link>
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
          {heroScreen && <FeaturedFacts key={cutPath(heroScreen)} title={heroScreen}/>}
          {status === "loading" && <p className="cinema-status" role="status">Loading recommendations…</p>}
          {status === "error" && <p className="cinema-status" role="status">The discovery catalogue is currently unavailable.</p>}
          <Section title="Continue where you left off" entries={continueEntries} onOpen={setDetail} href="/browse/library?status=current" />
          <Section title="Your watchlist" entries={savedEntries} onOpen={setDetail} href="/browse/library?status=watchlist" />
          <Section title="Recommended for you" entries={feed.slice(0, 8)} onOpen={setDetail} href="/browse/discover?status=recommended" />
          <Section title="Games" entries={feed.filter(entry => entry.item.media_type === "game").slice(0, 8)} onOpen={setDetail} href="/?view=game" />
          <Section title="Books" entries={feed.filter(entry => entry.item.media_type === "book").slice(0, 8)} onOpen={setDetail} href="/?view=book" />
        </>
      } />
      {detail && <TitleDetails entry={detail} saved={items.find(item =>
        item.media_type === detail.item.media_type && item.title.trim().toLowerCase() === detail.item.title.trim().toLowerCase()
      )} onClose={() => setDetail(null)} onSave={() => saveTitle(detail.item)} />}
    </>
  );
}
