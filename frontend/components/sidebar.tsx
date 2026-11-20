"use client";
import Link from "next/link";
import { Icon } from "./icons";
export const nav = [["home","Home"],["discover","Discover"],["movie","Movies"],["anime","Anime"],["tv","TV Shows"],["game","Games"],["book","Books"],["library","My Library"],["memory","Memory"],["data","Data"],["ai","AI"],["settings","Settings"]];
const routes: Record<string, string> = {
  home: "/",
  discover: "/browse/discover",
  movie: "/browse/movies",
  anime: "/browse/anime",
  tv: "/browse/tv",
  library: "/browse/library",
};

export function Sidebar({ active }: { active: string }) {
  return <aside className="sidebar">
    <div className="brand"><span className="brand-mark">M</span><span>Manu <i>AI</i></span></div>
    <nav aria-label="Main navigation">
      {nav.map(([id, label]) => (
        <Link key={id} href={routes[id] ?? `/?view=${id}`} aria-label={label} title={label}
          aria-current={active === id ? "page" : undefined}
          className={`nav-item ${active === id ? "active" : ""} ${id === "memory" ? "nav-split" : ""}`}>
          <Icon name={id === "library" ? "book" : id}/><span>{label}</span>
        </Link>
      ))}
      <a className="nav-item bridge-link" href="/memory-bridge" aria-label="ChatGPT Bridge" title="ChatGPT Bridge"><Icon name="memory"/><span>ChatGPT Bridge</span></a>
      <a className="nav-item bridge-link" href="/profile" aria-label="My AI Profile" title="My AI Profile"><Icon name="memory"/><span>My AI Profile</span></a>
    </nav>
    <div className="sidebar-bottom"><div className="private-dot"/><span>Private &amp; local</span></div>
  </aside>;
}
