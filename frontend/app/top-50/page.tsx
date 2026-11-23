"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { Artwork } from "@/components/cut/ui";
import { CardFacts, useTitleCard } from "@/components/cut/card-facts";
import { api } from "@/lib/api";
import { cutPath, type CutTitle } from "@/lib/cut";
import styles from "./ranking.module.css";

const categories = ["Movies", "Series", "Anime"] as const;
type Category = typeof categories[number];
type Pick = CutTitle & { note: string };

function RankedCard({ pick, rank }: { pick: Pick; rank: number }) {
  const card = useTitleCard(pick);
  const title = card.title;
  return <li value={rank}>
    <article className={styles.card} ref={card.ref}>
      <Link className={styles.poster} href={cutPath(title)} aria-label={`Open ${title.title}`}>
        <Artwork title={title}/>
        <b>#{rank}</b>
      </Link>
      <div className={styles.copy}>
        <small>{[title.release_year, title.genres].filter(Boolean).join(" · ")}</small>
        <h2><Link href={cutPath(title)}>{title.title}</Link></h2>
        <p>{pick.note}</p>
        <CardFacts {...card}/>
      </div>
    </article>
  </li>;
}

export default function Top50() {
  const [category, setCategory] = useState<Category>("Movies");
  const [page, setPage] = useState(0);
  const [rankings, setRankings] = useState<Record<Category, Pick[]>>();
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    api<Record<Category, Pick[]>>("/cinema/rankings", { signal: controller.signal })
      .then(setRankings)
      .catch(() => { if (!controller.signal.aborted) setError("The rankings could not be loaded."); });
    return () => controller.abort();
  }, []);

  const picks = rankings?.[category] ?? [];
  const start = page * 5;
  return <div className="shell cinema-shell"><Sidebar active="top50"/><main className="main cut">
    <div className={styles.wrap}>
      <h1>Your Top 50</h1>
      <p>Ranked for your taste in mind games, fast hooks, rival strategists and stories that pay off.</p>
      <nav className={styles.controls} aria-label="Recommendation category">{categories.map(name =>
        <button key={name} aria-pressed={category === name} onClick={() => { setCategory(name); setPage(0); }}>{name}</button>
      )}</nav>
      {error && <p role="alert">{error}</p>}
      {!rankings && !error && <p role="status">Loading rankings…</p>}
      {!!picks.length && <>
        <div className={styles.pager}>
          <strong aria-live="polite">{category} · {start + 1}–{Math.min(start + 5, picks.length)} of {picks.length}</strong>
          <button disabled={!page} onClick={() => setPage(page - 1)}>Previous</button>
          <button disabled={start + 5 >= picks.length} onClick={() => setPage(page + 1)}>Next</button>
        </div>
        <ol className={styles.list} start={start + 1}>{picks.slice(start, start + 5).map((pick, index) =>
          <RankedCard key={pick.id} pick={pick} rank={start + index + 1}/>
        )}</ol>
      </>}
    </div>
  </main></div>;
}
