"use client";
import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { Poster } from "@/components/cut/ui";
import { mediaTypes, type CutTitle } from "@/lib/cut";
import "./discovery.css";

type Candidate={item:{id:number;title:string;media_type:string;genres:string;description:string;image_url:string;imdb_rating:number|null;runtime:string;ott_india:string;intensity:string;ending_type:string;release_year:number|null};score:number;reasons:string[];source:string};
type WebResult={title:string;url:string;snippet:string;provider:string};

export default function DiscoveryPage(){
 const [items,setItems]=useState<Candidate[]>([]),[query,setQuery]=useState(""),[web,setWeb]=useState<WebResult[]>([]),[busy,setBusy]=useState(true),[searching,setSearching]=useState(false),[error,setError]=useState("");
 const load=async()=>{setBusy(true);try{const r=await fetch(`${API_URL}/discover?limit=18`);if(!r.ok)throw new Error("Discovery API unavailable");setItems(await r.json());}catch(e){setError(e instanceof Error?e.message:"Could not load discovery")}finally{setBusy(false)}};
 useEffect(()=>{load()},[]);
 const search=async(e:React.FormEvent)=>{e.preventDefault();if(!query.trim())return;setSearching(true);setError("");try{const [local,online]=await Promise.all([fetch(`${API_URL}/discover?query=${encodeURIComponent(query)}&limit=18`),fetch(`${API_URL}/discover/web?query=${encodeURIComponent(query)}&limit=8`)]);if(!local.ok||!online.ok)throw new Error("Live research failed");setItems(await local.json());setWeb((await online.json()).results||[])}catch(err){setError(err instanceof Error?err.message:"Live research failed")}finally{setSearching(false)}};
 return <main className="discovery-shell"><div className="discovery-noise"/><header><div className="wordmark"><span>✦</span> MANU’S <i>CUT</i></div><div className="status"><b/> YOUR TASTE <span>·</span> INDIA</div></header><section className="discovery-hero"><p className="kicker">TONIGHT’S PERSONAL SHORTLIST</p><h1>Find your next<br/><em>obsession.</em></h1><p>Movies, series and anime picked for your taste. Your saved library and recommendations remain private.</p><form onSubmit={search}><span>⌕</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search movies, TV series and anime…"/><button>{searching?"Researching…":"Explore"}</button></form>{error&&<small className="error">{error}</small>}</section>
 <section className="signal"><div><b>{busy?"—":items.length}</b><span>RECOMMENDATIONS</span></div><div><b>{web.length||"∞"}</b><span>WEB RESULTS</span></div><div><b>LOCAL</b><span>YOUR LIBRARY</span></div></section>
 <section className="results"><div className="section-top"><div><p className="kicker">TONIGHT’S SHORTLIST</p><h2>Your next <em>watch.</em></h2></div><span>Match measures fit, not your predicted /10 rating</span></div>{busy?<div className="skeleton-grid">{Array.from({length:6}).map((_,i)=><div className="skeleton" key={i}/>)}</div>:<div className="cards cut">{items.map((c,i)=>{
 const item = c.item;
 if (item.media_type in mediaTypes) {
  const media_type = item.media_type as CutTitle["media_type"];
  const source = c.source === "public_tmdb" ? media_type : "catalogue";
  return <Poster key={`${source}/${item.id}`} title={{...item, media_type, source, release_year: item.release_year ?? undefined}}/>;
 }
 return <article className="discover-card" key={c.item.id}><div className="poster" style={{backgroundImage:c.item.image_url?`url(${c.item.image_url})`:undefined}}><span>{String(i+1).padStart(2,"0")}</span><b>{c.score}% fit</b></div><div className="card-body"><div className="meta">{c.item.media_type} · {c.item.release_year||"Year unverified"}</div><h3>{c.item.title}</h3><p>{c.item.genres || "Genre unverified"}</p><div className="rating-grid"><div className="rating-stat"><span>IMDb</span><strong>{c.item.imdb_rating != null ? `${c.item.imdb_rating}/10` : "Unverified"}</strong></div><div className="rating-stat"><span>Personal match</span><strong>{Math.round(c.score)}% fit</strong></div></div><div className="watch-detail"><span>Watch time</span><b>{c.item.runtime || "Unverified"}</b></div><div className="watch-detail"><span>Where to watch in India</span><b>{c.item.ott_india || "Availability unverified"}</b></div>{c.reasons?.length>0&&<div className="why">✦ {c.reasons[0]}</div>}{c.item.intensity&&<div className="chips"><span>{c.item.intensity}</span></div>}</div></article>})}</div>}</section>
 {web.length>0&&<section className="web-section"><div><p className="kicker">LIVE RESEARCH</p><h2>The internet is <em>listening.</em></h2><p>These are public sources found for your current search. They are not treated as personal facts.</p></div><div className="web-list">{web.map((r,i)=><a href={r.url} target="_blank" rel="noreferrer" key={r.url}><span>0{i+1}</span><div><b>{r.title}</b><small>{r.snippet}</small></div><strong>↗</strong></a>)}</div></section>}
 <footer>YOUR LIBRARY STAYS LOCAL <span>◆</span> AVAILABILITY MAY NEED VERIFICATION</footer></main>
}
