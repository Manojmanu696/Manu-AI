"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import HomeFeed from "@/components/home-feed";
import { api } from "@/lib/api";
import "./discovery.css";

type WebResult = { title: string; url: string; snippet: string; provider: string };

export default function DiscoveryPage() {
  const [query, setQuery] = useState("");
  const [web, setWeb] = useState<WebResult[]>([]);
  const [report, setReport] = useState("");
  const [searching, setSearching] = useState(false);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const term = query.trim();
    if (term.length < 2) return;
    setSearching(true);
    setReport("");
    setWeb([]);
    try {
      const response = await api<{results: WebResult[]}>(`/discover/web?query=${encodeURIComponent(term)}&limit=8`);
      setWeb(response.results);
      if (!response.results.length) setReport("No public sources found.");
    } catch (error) {
      setReport(error instanceof Error ? error.message : "Web search is unavailable.");
    } finally {
      setSearching(false);
    }
  }

  return <main className="standalone-discovery">
    <header className="discovery-top"><Link href="/">Manu AI</Link><a href="#web-research">Web research</a></header>
    <HomeFeed discover/>
    <section className="web-research" id="web-research">
      <h2>Web research</h2>
      <form onSubmit={search}>
        <label htmlFor="web-query">Search public sources</label>
        <div><input id="web-query" type="search" required minLength={2} value={query} onChange={event => setQuery(event.target.value)}/><button className="primary-button" disabled={searching}>{searching ? "Searching…" : "Search web"}</button></div>
      </form>
      {report && <p role="status">{report}</p>}
      {web.length > 0 && <ul>{web.map(result => <li key={result.url}>
        <a href={result.url} target="_blank" rel="noopener noreferrer">{result.title} ↗</a>
        {result.snippet && <p>{result.snippet}</p>}
        <small>{result.provider}</small>
      </li>)}</ul>}
    </section>
  </main>;
}
