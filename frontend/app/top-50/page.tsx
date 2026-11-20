"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { api } from "@/lib/api";
import rankings from "@/lib/top50.json";
import styles from "./ranking.module.css";

type Category = keyof typeof rankings;
type Pick = (typeof rankings)["Movies"][number];
type Metadata = {
  title: string; release_year?: number; media_type: string; image_url?: string;
  genres?: string; runtime?: string; episodes?: number; languages?: string;
  episode_duration?: string; seasons?: number;
};
const categories: Category[] = ["Movies", "Series", "Anime"];
const mediaType = { Movies: "movie", Series: "tv", Anime: "anime" };
const normalize = (title: string) => title.normalize("NFKD").toLowerCase().replace(/[^a-z0-9]/g, "");

function RankedCard({ pick, rank, category }: { pick: Pick; rank: number; category: Category }) {
  const [metadata, setMetadata] = useState<Metadata>();
  const [imageFailed, setImageFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const type = mediaType[category];
    const params = new URLSearchParams({ media_type: type, query: pick.title, limit: "8" });
    api<{ item: Metadata }[]>("/discover?" + params, { signal: controller.signal })
      .then(rows => {
        const match = rows.find(({ item }) => normalize(item.title) === normalize(pick.title) && item.release_year === pick.year && item.media_type === type);
        if (!controller.signal.aborted) setMetadata(match?.item);
      }).catch(() => {});
    return () => controller.abort();
  }, [pick.title, pick.year, category]);

  return <li className={styles.card} value={rank}>
    <div className={styles.poster}>
      {metadata?.image_url && !imageFailed && <img src={metadata.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)} />}
      <b>#{rank}</b>
    </div>
    <div>
      <small>{pick.year}{metadata?.genres && " · " + metadata.genres}</small>
      <h2>{pick.title}</h2>
      <p>{pick.note}</p>
      {metadata && <small>{[metadata.runtime, metadata.seasons && metadata.seasons + " seasons", metadata.episodes && metadata.episodes + " episodes", metadata.languages].filter(Boolean).join(" · ")}</small>}
      <a href={"https://www.justwatch.com/in/search?q=" + encodeURIComponent(pick.title)} target="_blank" rel="noreferrer">Check streaming in India ↗</a>
    </div>
  </li>;
}

export default function Top50() {
  const [category, setCategory] = useState<Category>("Movies");
  const [page, setPage] = useState(0);
  const start = page * 5;
  return <div className="shell cinema-shell"><Sidebar active="top50"/><main className="main">
    <div className={styles.wrap}>
      <h1>Your Top 50</h1>
      <p>Ranked for your taste in mind games, fast hooks, rival strategists and stories that pay off.</p>
      <nav className={styles.controls} aria-label="Recommendation category">{categories.map(name =>
        <button key={name} aria-pressed={category === name} onClick={() => { setCategory(name); setPage(0); }}>{name}</button>
      )}</nav>
      <div className={styles.pager}>
        <strong aria-live="polite">{category} · {start + 1}–{start + 5} of 50</strong>
        <button disabled={!page} onClick={() => setPage(page - 1)}>Previous</button>
        <button disabled={page === 9} onClick={() => setPage(page + 1)}>Next</button>
      </div>
      <ol className={styles.list} start={start + 1}>{rankings[category].slice(start, start + 5).map((pick, index) =>
        <RankedCard key={category + pick.title} pick={pick} rank={start + index + 1} category={category}/>
      )}</ol>
    </div>
  </main></div>;
}
