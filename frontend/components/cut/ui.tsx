"use client";

import Link from "next/link";
import { Sidebar } from "@/components/sidebar";
import { usePathname, useRouter } from "next/navigation";
import { useRef, useState, type ReactNode } from "react";
import { cardRating, cutPath, mediaTypes, safeUrl, statuses, type CutTitle } from "@/lib/cut";

const glyphs = {
  film: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4m-4 6h4m10-6h4m-4 6h4"/></>,
  search: <><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></>,
  bookmark: <path d="M6 5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v15l-6-4-6 4z"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  arrow: <path d="M4 12h15m-6-6 6 6-6 6"/>,
  back: <path d="M20 12H5m6-6-6 6 6 6"/>,
  left: <path d="m15 6-6 6 6 6"/>,
  right: <path d="m9 6 6 6-6 6"/>,
  play: <path d="m8 5 12 7-12 7z" fill="currentColor" stroke="none"/>,
  star: <path d="m12 2 2.9 6 6.6.9-4.7 4.6 1.1 6.5-5.9-3.1-5.9 3.1 1.1-6.5-4.7-4.6 6.6-.9z" fill="currentColor" stroke="none"/>,
  plus: <path d="M12 5v14M5 12h14"/>,
  pen: <><path d="m14 6 4 4M5 19l4-.8L20 7l-4-4L5 14z"/><path d="M12 20h8"/></>,
  close: <path d="m6 6 12 12M18 6 6 18"/>,
  clock: <><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></>,
  outward: <path d="M7 17 17 7M7 7h10v10"/>,
  journal: <><path d="M5 5a2 2 0 0 1 2-2h13v17H7a2 2 0 0 1-2-2z"/><path d="M5 17c0-1 1-2 2-2h13M9 7h6m-6 4h6"/></>,
  sliders: <><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2" fill="var(--cut-bg)"/><circle cx="15" cy="17" r="2" fill="var(--cut-bg)"/></>,
};
export function Glyph({ name, size = 20 }: { name: keyof typeof glyphs; size?: number }) {
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{glyphs[name]}</svg>;
}

const activeSections: Record<string, string> = {
  "/browse/discover": "discover",
  "/browse/movies": "movie",
  "/browse/tv": "tv",
  "/browse/anime": "anime",
  "/browse/library": "library",
  "/browse/reviews": "library",
};

export function CutFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState("");
  return (
    <div className="shell cinema-shell">
      <Sidebar active={activeSections[pathname] ?? ""}/>
      <div className="main cut cut-shell-content">
        <a className="cut-skip" href="#cut-main">Skip to content</a>
        <header className="cut-header">
          <div className="cut-header-inner">
            <Link className="cut-brand" href="/" aria-label="Manu’s Cut home">Manu’s Cut<span className="cut-brand-mark" aria-hidden="true"/></Link>
            <div className="cut-header-tools">
              <form className="cut-quick-search" role="search" aria-label="Search titles" onSubmit={event => {
                event.preventDefault();
                router.push(query.trim() ? `/browse/discover?q=${encodeURIComponent(query.trim())}` : "/browse/discover");
              }}>
                <button type="submit" aria-label="Search titles"><Glyph name="search" size={19}/></button>
                <input aria-label="Search movies, TV and anime" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search titles" maxLength={200}/>
              </form>
              <Link className="cut-mobile-search" href="/browse/discover#title-search" aria-label="Search titles"><Glyph name="search"/></Link>
            </div>
          </div>
        </header>
        <main id="cut-main" tabIndex={-1}>{children}</main>
        <footer className="cut-footer"><div className="cut-container"><Link className="cut-footer-brand" href="/">Manu’s Cut</Link><nav aria-label="Manu AI tools"><Link href="/?view=ai">Manu AI tools</Link><Link href="/profile">Taste profile</Link><Link href="/memory-bridge">Memory bridge</Link></nav></div></footer>
      </div>
    </div>
  );
}

function tmdbSizes(url: string, sizes: string[]) {
  return sizes.map(size => url.replace(/\/t\/p\/w\d+\//, `/t/p/w${size}/`) + ` ${size}w`).join(", ");
}

export function Artwork({ title, backdrop = false, eager = false, sizes }: { title: CutTitle; backdrop?: boolean; eager?: boolean; sizes?: string }) {
  const url = safeUrl(backdrop ? title.backdrop_url || title.image_url : title.image_url);
  const [failed, setFailed] = useState<string>();
  const wide = backdrop && !!title.backdrop_url;
  const tmdb = url?.startsWith("https://image.tmdb.org/t/p/") && /\/w\d+\//.test(url);
  return (
    <span className={`cut-art ${backdrop ? "cut-art-wide" : ""} ${wide ? "has-backdrop" : ""}`} data-media={title.media_type}>
      {url && failed !== url
        // TMDB supplies width-specific art directly. Stored imagery can come from arbitrary hosts.
        // eslint-disable-next-line @next/next/no-img-element
        ? <img src={url} srcSet={tmdb ? tmdbSizes(url, wide ? ["780", "1280"] : ["185", "342", "500"]) : undefined}
            sizes={tmdb ? (wide ? sizes || "100vw" : "(max-width: 540px) 45vw, (max-width: 950px) 24vw, 220px") : undefined}
            alt="" loading={eager ? "eager" : "lazy"} fetchPriority={eager ? "high" : "auto"} decoding="async" onError={() => setFailed(url)}/>
        : <span className="cut-art-fallback" aria-label={backdrop ? undefined : "No poster available"}><Glyph name="film" size={35}/>{!backdrop && <span>{mediaTypes[title.media_type]}</span>}</span>}
    </span>
  );
}

export function Poster({ title, pending, onSave }: { title: CutTitle; pending?: boolean; onSave?: (title: CutTitle) => void }) {
  const rating = cardRating(title);
  return (
    <article className="cut-poster">
      <Link href={cutPath(title)} className="cut-poster-link">
        <div className="cut-poster-image">
          <Artwork title={title}/>
          {rating && <span className="cut-card-rating" title={rating.source}><Glyph name="star" size={13}/><span className="cut-sr">{rating.source} </span>{rating.value.toFixed(1)}</span>}
        </div>
        <h3>{title.title}</h3>
        <div className="cut-poster-meta">{[title.release_year, mediaTypes[title.media_type]].filter(Boolean).join(" · ")}</div>
      </Link>
      {onSave && (!title.media_id || title.status === "recommended"
        ? <button className="cut-card-save" type="button" disabled={pending} onClick={() => onSave(title)} aria-label={`Save ${title.title} to watchlist`} title="Save to watchlist"><Glyph name="bookmark" size={18}/></button>
        : <Link className="cut-card-save is-saved" href={cutPath(title)} title={title.status ? statuses[title.status] : "In your library"} aria-label={`${title.title} is in your library. Open title`}><Glyph name="check" size={18}/></Link>)}
    </article>
  );
}

export function Shelf({ name, href, titles, saving, onSave }: {
  name: string; href?: string; titles: CutTitle[]; saving?: string; onSave?: (entry: CutTitle) => void;
}) {
  const track = useRef<HTMLDivElement>(null);
  if (!titles.length) return null;
  const scroll = (direction: number) => track.current?.scrollBy({ left: direction * (track.current.clientWidth * .9) });
  return (
    <section className="cut-shelf" aria-label={name}>
      <div className="cut-shelf-top"><h2>{name}</h2><div className="cut-shelf-actions">
        {href && <Link href={href}>View all <Glyph name="arrow" size={17}/></Link>}
        {titles.length > 2 && <><button onClick={() => scroll(-1)} aria-label={`Scroll ${name} left`}><Glyph name="left" size={16}/></button><button onClick={() => scroll(1)} aria-label={`Scroll ${name} right`}><Glyph name="right" size={16}/></button></>}
      </div></div>
      <div className="cut-track" ref={track}>
        {titles.map(title => <Poster key={cutPath(title)} title={title} pending={saving === cutPath(title)} onSave={onSave}/>)}
      </div>
    </section>
  );
}

export function StatePanel({ title, children, error = false }: { title: string; children?: ReactNode; error?: boolean }) {
  return <div className="cut-state" role={error ? "alert" : undefined}><Glyph name={error ? "clock" : "film"} size={30}/><h2>{title}</h2>{children}</div>;
}

export function TagList({ tags }: { tags: string[] }) {
  return tags.length > 0 && <ul className="cut-tags" aria-label="Tags">{tags.map((tag, index) => <li key={`${tag}-${index}`}>{tag}</li>)}</ul>;
}
