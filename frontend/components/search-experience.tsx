"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Poster } from "./cut/ui";
import { CutTitle, cutPath, mediaTypes, messageFrom } from "@/lib/cut";

export default function SearchExperience({ browse }: { browse: ReactNode }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [titles, setTitles] = useState<CutTitle[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      request.current?.abort();
    };
  }, []);

  async function search(event: FormEvent) {
    event.preventDefault();
    const text = query.trim();
    if (text.length < 2) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setSubmitted(text);
    setBusy(true);
    setError("");
    setTitles([]);
    try {
      const params = new URLSearchParams({ query: text, media_type: category });
      const results = await api<CutTitle[]>(`/cinema/search?${params}`, { signal: controller.signal });
      if (!controller.signal.aborted) setTitles(results);
    } catch (failure) {
      if (!controller.signal.aborted) setError(messageFrom(failure));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  function backToBrowse() {
    request.current?.abort();
    setSubmitted("");
    setBusy(false);
    setError("");
  }

  return <section className="search-experience cinema-search" aria-label="Title search">
    <header className="cinema-search-bar">
      <form className="global-search" role="search" onSubmit={search}>
        <span className="search-icon" aria-hidden="true">⌕</span>
        <input ref={input} type="search" value={query} onChange={event => setQuery(event.target.value)}
          placeholder="Search movies, series and anime" aria-label="Search titles" minLength={2} maxLength={200} required/>
        <button className="global-submit" type="submit" disabled={busy} aria-label="Run search">{busy ? "…" : "→"}</button>
      </form>
      <label className="cinema-search-filter"><span>Category</span><select value={category} onChange={event => setCategory(event.target.value)}>
        <option value="">All titles</option>
        {Object.entries(mediaTypes).map(([type, label]) => <option key={type} value={type}>{label}</option>)}
      </select></label>
      <Link className="cinema-profile" href="/profile" aria-label="My AI profile">M</Link>
      {submitted && <button className="cinema-button" onClick={backToBrowse}>Back to browse</button>}
    </header>
    {!submitted ? browse : <section className="cinema-title-results" aria-busy={busy}>
      <h2>Titles matching “{submitted}”</h2>
      {busy && <p role="status">Looking up titles…</p>}
      {error && <p role="alert">{error}</p>}
      {!busy && !error && !titles.length && <p>No matching titles found. Try another spelling or category.</p>}
      <div className="cut cut-grid cinema-title-cards">
        {titles.map(title => <Poster key={cutPath(title)} title={title}/>)}
      </div>
    </section>}
  </section>;
}
