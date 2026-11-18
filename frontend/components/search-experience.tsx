"use client";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Mode="ai"|"google";
type SearchResult={title:string;url:string;snippet?:string;provider?:string};
type DiscoveryItem={id:number;media_type:string;title:string;description?:string;genres?:string;release_year?:number|null;image_url?:string;imdb_rating?:number|null;public_rating?:number|null;runtime?:string;ott_india?:string;seasons?:number|null;episodes?:number|null;episode_duration?:string;languages?:string;watch_url?:string;source_url?:string;source?:string;trailer_url?:string};
type DiscoveryResult={item:DiscoveryItem;score:number;reasons:string[];source?:string};
type ChatResult={answer?:string;facts?:string[]};
const CATEGORIES=[{id:"all",label:"All",icon:"⌕"},{id:"movie",label:"Movies",icon:"🎬"},{id:"anime",label:"Anime",icon:"✦"},{id:"tv",label:"TV Shows",icon:"▣"},{id:"game",label:"Games",icon:"◉"},{id:"book",label:"Books",icon:"▰"},{id:"video",label:"Videos",icon:"▶"},{id:"news",label:"News",icon:"⌁"},{id:"website",label:"Websites",icon:"↗"}] as const;
const mediaWords:Record<string,string[]>={movie:["movie","movies","film","films","cinema"],anime:["anime","manga"],tv:["tv","show","shows","series","season","episode"],game:["game","games","gaming","steam","xbox","playstation"],book:["book","books","novel","novels","reading"]};
function infer(q:string){const words=q.toLowerCase().replace(/[^a-z0-9]+/g," ").split(/\s+/);for(const [type,keys] of Object.entries(mediaWords))if(keys.some(k=>words.includes(k)))return type;return "all"}
function googleUrl(q:string,cat:string){const extra=cat==="movie"?" movies":cat==="anime"?" anime":cat==="tv"?" TV series":cat==="game"?" video games":cat==="book"?" books":cat==="video"?" videos":cat==="news"?" news":"";return `https://www.google.com/search?q=${encodeURIComponent(q+extra)}`}

export default function SearchExperience({browse}: {browse: ReactNode}){
const[mode,setMode]=useState<Mode>("ai"),[category,setCategory]=useState("all"),[query,setQuery]=useState(""),[results,setResults]=useState<SearchResult[]>([]),[discovery,setDiscovery]=useState<DiscoveryResult[]>([]),[answer,setAnswer]=useState<ChatResult|null>(null),[busy,setBusy]=useState(false),[searched,setSearched]=useState(false),[error,setError]=useState("");
 useEffect(()=>{const h=(e:KeyboardEvent)=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){e.preventDefault();document.querySelector<HTMLInputElement>(".global-search input")?.focus()}};window.addEventListener("keydown",h);return()=>window.removeEventListener("keydown",h)},[]);
 async function runSearch(e?:FormEvent,forcedQuery?:string,forcedCategory?:string){e?.preventDefault();const text=(forcedQuery??query).trim();if(!text||busy)return;const selected=forcedCategory??category;const inferred=selected==="all"?infer(text):selected;setQuery(text);setCategory(inferred);setSearched(true);setBusy(true);setError("");setAnswer(null);setResults([]);setDiscovery([]);
   if(mode==="google")window.open(googleUrl(text,inferred),"_blank","noopener,noreferrer");
   try{
     if(["movie","anime","tv","game","book"].includes(inferred)){const p=new URLSearchParams({media_type:inferred,limit:"18",query:text});const d=await api<DiscoveryResult[]>(`/discover?${p}`);setDiscovery(d||[])}
     let web:{results:SearchResult[]}={results:[]};try{web=await api<{results:SearchResult[]}>(`/research/search`,{method:"POST",body:JSON.stringify({query:text})});setResults(web.results||[])}catch(err){if(mode==="ai")throw err;setError("Google was opened for the full web. Structured media results are shown here when available.")}
     if(mode==="ai"&&inferred==="all"&&web.results?.length){const evidence=web.results.slice(0,8).map((r,i)=>`${i+1}. ${r.title}\n${r.snippet||""}\n${r.url}`).join("\n\n");const a=await api<ChatResult>("/chat",{method:"POST",body:JSON.stringify({message:`Answer this query using the fresh public web evidence below. Do not invent facts. Query: ${text}\n\n${evidence}`})});setAnswer(a)}
   }catch(err){setError(err instanceof Error?err.message:"Search failed")}finally{setBusy(false)}
 }
 const catLabel=CATEGORIES.find(c=>c.id===category)?.label||"All";
 return <section className="search-experience cinema-search" aria-label="Manu AI search">
 <header className="cinema-search-bar">
   <form className="global-search" onSubmit={runSearch}>
     <span className="search-icon" aria-hidden="true">⌕</span>
     <input type="search" value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search titles or ask Manu" aria-label="Search titles or ask Manu"/>
     <button className="global-submit" type="submit" disabled={busy} aria-label="Run search">{busy?"…":"→"}</button>
   </form>
   <label className="cinema-search-filter"><span>Search with</span><select value={mode} onChange={event=>setMode(event.target.value as Mode)}><option value="ai">Manu AI</option><option value="google">Google</option></select></label>
   <label className="cinema-search-filter"><span>Category</span><select value={category} onChange={event=>setCategory(event.target.value)}>{CATEGORIES.map(({id,label})=><option key={id} value={id}>{label}</option>)}</select></label>
   <a className="cinema-profile" href="/profile" aria-label="My AI profile">M</a>
   {searched&&<button className="cinema-button" disabled={busy} onClick={()=>{setSearched(false);setError("")}}>Back to browse</button>}
 </header>
 {error&&<div className="search-error" role="alert">{error}</div>}
 {!searched&&browse}
 {searched&&<div className="search-content">
 {answer&&mode==="ai"&&<article className="search-ai-answer"><div className="answer-label">MANU AI · WEB-AUGMENTED</div><p>{answer.answer}</p>{answer.facts?.length?<div className="answer-facts">{answer.facts.slice(0,5).map(f=><span key={f}>✓ {f}</span>)}</div>:null}</article>}
 {discovery.length>0&&<section className="discovery-results"><div className="results-title"><div><span>PERSONALIZED {catLabel.toUpperCase()}</span><h2>{catLabel} matches for “{query}”</h2></div><div className="result-actions"><span>{discovery.length} cards</span><button onClick={()=>window.open(googleUrl(query,category),"_blank","noopener,noreferrer")}>Google ↗</button></div></div><div className="media-discovery-grid">{discovery.map(r=><DiscoveryCard key={`${r.item.id}-${r.item.title}`} result={r}/>)}</div></section>}
 <section className="web-results-block"><div className="results-title"><div><span>WEB RESULTS</span><h2>{results.length?`Results for “${query}”`:mode==="google"?"Google search opened":"No web results"}</h2></div>{mode==="google"&&<button onClick={()=>window.open(googleUrl(query,category),"_blank","noopener,noreferrer")}>Open Google ↗</button>}</div>{results.map(r=><a className="search-result-card" key={`${r.url}-${r.title}`} href={r.url} target="_blank" rel="noreferrer"><small>{(()=>{try{return new URL(r.url).hostname}catch{return r.url}})()}</small><h3>{r.title}</h3><p>{r.snippet||"Open result"}</p></a>)}{!results.length&&!discovery.length&&mode!=="google"&&<div className="no-results-card">No public results returned. Configure a web-search provider in your local environment or use Google.</div>}</section></div>}
 <footer className="search-footer"><span>Private library stays local</span><span>Web search on demand</span><span>AI uses fresh public evidence</span></footer></section>
}

function DiscoveryCard({result}:{result:DiscoveryResult}){const i=result.item;const series=i.media_type==="tv"||i.media_type==="anime";return <article className="discovery-card"><div className="discovery-poster">{i.image_url?<img src={i.image_url} alt={`${i.title} poster`}/>:<strong>{i.title.slice(0,1)}</strong>}<b>{result.score}% match</b></div><div className="discovery-card-body"><div className="card-title-row"><div><h3>{i.title}</h3><p>{i.release_year||"—"} · {i.genres||i.media_type}</p></div>{i.imdb_rating?<strong className="imdb">IMDb {i.imdb_rating}</strong>:null}</div><p className="card-description">{i.description||"No synopsis available."}</p><div className="meta-pills">{i.public_rating?<span>★ {i.public_rating}</span>:null}{i.runtime?<span>⏱ {i.runtime}</span>:null}{i.ott_india?<span>▣ {i.ott_india}</span>:null}{series&&i.seasons?<span>▤ {i.seasons} seasons</span>:null}{series&&i.episodes?<span>• {i.episodes} episodes</span>:null}{series&&i.episode_duration?<span>⌛ {i.episode_duration}</span>:null}</div>{i.languages&&<p className="language-line">🌐 <strong>Languages:</strong> {i.languages}</p>}<p className="fit-reason">✦ {result.reasons?.[0]||"Matches your saved taste."}</p><div className="discovery-actions">{i.watch_url&&<a className="watch-button" href={i.watch_url} target="_blank" rel="noreferrer">▶ Where to watch ↗</a>}{i.trailer_url&&<a className="details-button" href={i.trailer_url} target="_blank" rel="noreferrer">Trailer ↗</a>}{i.source_url&&<a className="details-button" href={i.source_url} target="_blank" rel="noreferrer">Details ↗</a>}</div><div className="source-line">{i.source||"public"} · metadata checked live</div></div></article>}
