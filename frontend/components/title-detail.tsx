"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { API_URL } from "@/lib/api";
import "./title-detail.css";

type Title = {
  id:number; media_type:string; title:string; original_title?:string; description?:string; genres?:string;
  release_year?:number|null; image_url?:string; backdrop_url?:string; public_rating?:number|null; imdb_rating?:number|null;
  vote_count?:number; runtime?:string; seasons?:number|null; episodes?:number|null; episode_duration?:string;
  series_status?:string; original_language?:string; source_provider?:string; source_url?:string; external_url?:string;
  watch_url?:string; watch_providers_json?:string; credits_json?:string; trailer_url?:string; ott_india?:string;
  detail_error?:string; recommendation?:{label:string;reasons:string[];caveats?:string[]}; personal?:{status:string;rating:number|null;notes:string}|null;
  similar_titles?:{item:{id:number;title:string;image_url?:string;release_year?:number|null;genres?:string};fit:string;reasons:string[]}[];
  episode_details_json?:string; schedule_json?:string; countries_json?:string;
};
type Provider = {name:string;type:string;logo?:string};

async function api<T>(path:string,init?:RequestInit):Promise<T>{
  const response=await fetch(`${API_URL}${path}`,{...init,headers:{"Content-Type":"application/json",...(init?.headers||{})}});
  if(!response.ok)throw new Error((await response.json().catch(()=>({}))).detail||`Request failed (${response.status})`);
  return response.status===204?undefined as T:response.json();
}
function safe(url?:string){return url&&/^https:\/\/(image\.tmdb\.org|s4\.anilist\.co|static\.tvmaze\.com)\//.test(url)?url:"";}

export default function TitleDetail(){
  const params=useParams<{id:string}>(); const router=useRouter();
  const [item,setItem]=useState<Title|null>(null),[busy,setBusy]=useState(true),[error,setError]=useState(""),[status,setStatus]=useState(""),[reason,setReason]=useState(""),[rating,setRating]=useState("8");
  useEffect(()=>{let active=true;api<Title>(`/catalogue/${params.id}`).then(value=>{if(active)setItem(value)}).catch(e=>{if(active)setError(e instanceof Error?e.message:"This title could not be loaded")}).finally(()=>{if(active)setBusy(false)});return()=>{active=false}},[params.id]);
  async function act(action:string,extra:{reason?:string;rating?:number}={}){if(!item)return;setStatus("Saving…");try{await api(`/discover/${item.id}/feedback`,{method:"POST",body:JSON.stringify({action,context:"title_detail",...extra})});setStatus(action==="watchlist"?"Added to your watchlist":"Saved to your local history");const updated=await api<Title>(`/catalogue/${item.id}`);setItem(updated)}catch(e){setStatus(e instanceof Error?e.message:"Could not save your action")}}
  if(busy)return <main className="title-page"><button className="title-back" onClick={()=>router.back()}>← Back to discovery</button><div className="title-loading"><div/><span>Loading title details…</span></div></main>;
  if(error||!item)return <main className="title-page"><button className="title-back" onClick={()=>router.back()}>← Back to discovery</button><div className="title-error"><h1>Title unavailable</h1><p>{error||"This title is no longer in the local catalogue."}</p><Link href="/">Return to Manu AI</Link></div></main>;
  let providers:Provider[]=[];let credits:{cast?:string[];directors?:string[];creators?:string[]}={};
  let episodeDetails:{season?:number;number?:number;airdate?:string;runtime?:number}[]=[];let schedule:{time?:string;days?:string[]}={};let countries:string[]=[];
  try{providers=JSON.parse(item.watch_providers_json||"[]")}catch{providers=[]}
  try{credits=JSON.parse(item.credits_json||"{}")}catch{credits={}}
  try{episodeDetails=JSON.parse(item.episode_details_json||"[]")}catch{episodeDetails=[]}
  try{schedule=JSON.parse(item.schedule_json||"{}")}catch{schedule={}}
  try{countries=JSON.parse(item.countries_json||"[]")}catch{countries=[]}
  const similarTitles=item.similar_titles||[];
  const ratingLabel=item.source_provider==="anilist"?"AniList score":item.source_provider==="tvmaze"?"TVmaze rating":"TMDB rating";
  const sourceLink=safeExternal(item.source_url||item.external_url);
  const trailerLink=safeExternal(item.trailer_url,["youtube.com","www.youtube.com","youtu.be"]);
  const watchLink=safeExternal(item.watch_url,["themoviedb.org"]);
  return <main className="title-page">
    <div className="title-topline"><button className="title-back" onClick={()=>router.back()}>← Back to discovery</button><span>MANU AI <i>·</i> TITLE DETAILS</span></div>
    <section className="title-hero" style={safe(item.backdrop_url)?{backgroundImage:`linear-gradient(90deg,#121315 0%,rgba(18,19,21,.93) 40%,rgba(18,19,21,.52)),url("${safe(item.backdrop_url)}")`}:undefined}>
      {safe(item.image_url)&&<img className="title-poster" src={safe(item.image_url)} alt={`${item.title} poster`}/>}
      <div className="title-hero-copy"><p className="title-eyebrow">{item.media_type.toUpperCase()} <span>·</span> {item.recommendation?.label||"DISCOVERY"}</p><h1>{item.title}</h1>{item.original_title&&item.original_title!==item.title&&<p className="original-title">{item.original_title}</p>}
        <p className="title-facts">{item.release_year||""}{item.release_year&&item.genres?" · ":""}{item.genres||""}{item.runtime?` · ${item.runtime}`:""}{item.seasons?` · ${item.seasons} seasons`:""}{item.episodes?` · ${item.episodes} episodes`:""}{item.series_status?` · ${item.series_status}`:""}{item.original_language?` · ${item.original_language.toUpperCase()}`:""}{countries.length?` · ${countries.join(", ")}`:""}</p>
        {item.public_rating!=null&&<p className="title-rating"><strong>{item.public_rating.toFixed(1)}</strong><span>{ratingLabel}{item.vote_count?` · ${item.vote_count.toLocaleString()} votes`:""}</span></p>}
        <p className="title-synopsis">{item.description||"No synopsis was supplied by this catalogue provider."}</p>
        <div className="title-actions"><button onClick={()=>act("watchlist")}>Add to watchlist</button><button onClick={()=>act("started")}>Started</button><button onClick={()=>act("already_watched")}>Already watched</button><button onClick={()=>act("love")}>Love it</button><button onClick={()=>act("dropped")}>Dropped</button></div>
        {status&&<p className="title-action-status" role="status">{status}</p>}
      </div>
    </section>
    {item.detail_error&&<p className="title-detail-note">Some optional live details could not be refreshed. Showing saved catalogue information.</p>}
    <div className="title-detail-grid">
      <section className="title-info-section"><h2>Why it might fit</h2><ul>{(item.recommendation?.reasons||[]).map((x,i)=><li key={`${x}-${i}`}>{x}</li>)}</ul><h3 className="title-subhead">Possible mismatch</h3><ul>{(item.recommendation?.caveats||["No clear mismatch is present in the available catalogue details."]).map((x,i)=><li key={`caveat-${i}`}>{x}</li>)}</ul><p className="spoiler-note">Explanations use public metadata and your local preference signals. Plot outcomes are kept out.</p></section>
      <section className="title-info-section"><h2>For after watching</h2><p>Completion is stored separately from how much you enjoyed it.</p><div className="rating-row"><label htmlFor="rating">Rate from 1 to 10</label><select id="rating" value={rating} onChange={e=>setRating(e.target.value)}>{Array.from({length:10},(_,i)=><option key={i+1} value={i+1}>{i+1}</option>)}</select><button onClick={()=>act("rate",{rating:Number(rating)})}>Save rating</button><button className="quiet-action" onClick={()=>act("completed")}>Mark completed, unrated</button></div><label className="reason-label">If it is not for you, what missed? <select value={reason} onChange={e=>setReason(e.target.value)}><option value="">Choose an optional reason</option><option value="too_slow">Too slow</option><option value="too_emotional">Too emotional</option><option value="predictable">Too predictable</option><option value="wrong_genre">Wrong genre</option><option value="poor_writing">Poor writing</option><option value="mood">Not my current mood</option></select></label><button className="not-for-me" onClick={()=>act("not_interested",{reason})}>Not for me</button></section>
      {sourceLink&&<section className="title-info-section"><h2>Source</h2><p>Metadata supplied by {item.source_provider||"the public catalogue"}.</p><a href={sourceLink} target="_blank" rel="noreferrer">View source ↗</a>{trailerLink&&<a href={trailerLink} target="_blank" rel="noreferrer">Watch trailer ↗</a>}</section>}
      {providers.length>0&&<section className="title-info-section"><h2>Where to watch in India</h2><p>Provider listings can change. Check the current listing before watching.</p><div className="provider-list">{providers.map((p,i)=><span key={`${p.name}-${p.type}-${i}`}>{p.name}<small>{providerType(p.type)}</small></span>)}</div>{watchLink&&<a href={watchLink} target="_blank" rel="noreferrer">Check current availability ↗</a>}<small className="justwatch-credit">Streaming data by <a href="https://www.justwatch.com/in" target="_blank" rel="noreferrer">JustWatch</a>, through TMDB. Availability may change.</small></section>}
      {(Boolean(credits.cast?.length)||Boolean(credits.directors?.length)||Boolean(credits.creators?.length))&&<section className="title-info-section"><h2>People</h2>{Boolean(credits.directors?.length)&&<p><b>Director</b> {credits.directors!.join(", ")}</p>}{Boolean(credits.creators?.length)&&<p><b>Created by</b> {credits.creators!.join(", ")}</p>}{Boolean(credits.cast?.length)&&<p><b>Cast</b> {credits.cast!.join(", ")}</p>}</section>}
      {(episodeDetails.length>0||schedule.days?.length)&&<section className="title-info-section"><h2>Episodes & schedule</h2>{schedule.days?.length&&<p>Usually airs {schedule.days.join(", ")}{schedule.time?` at ${schedule.time}`:""}.</p>}{episodeDetails.length>0&&<ol className="episode-list">{episodeDetails.slice(0,8).map((episode,index)=><li key={`${episode.season}-${episode.number}-${index}`}>Season {episode.season??"—"}, episode {episode.number??index+1}{episode.airdate?` · ${episode.airdate}`:""}{episode.runtime?` · ${episode.runtime} min`:""}</li>)}</ol>}</section>}
      {item.personal&&<section className="title-info-section"><h2>Your notes</h2><p>Status: {item.personal.status.replace("_"," ")}{item.personal.rating?` · Your rating ${item.personal.rating}/10`:""}</p>{item.personal.notes&&<p>{item.personal.notes}</p>}</section>}
      {similarTitles.length>0&&<section className="title-info-section similar-section"><h2>Similar titles</h2><div className="similar-list">{similarTitles.map(({item:similar,fit})=><a href={`/title/${similar.id}`} key={similar.id}><span>{similar.title}</span><small>{similar.release_year||""}{similar.release_year&&similar.genres?" · ":""}{similar.genres||""} · {fit}</small></a>)}</div></section>}
    </div>
    <footer className="title-credits">{item.source_provider==="tmdb"&&<><a href="https://www.themoviedb.org" target="_blank" rel="noreferrer"><img src="https://www.themoviedb.org/assets/v4/logos/v2/blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg" alt="TMDB" width="78" height="16"/></a><span>This product uses the TMDB API but is not endorsed or certified by TMDB.</span></>}{item.source_provider==="tvmaze"&&<span>TV data provided by <a href="https://www.tvmaze.com" target="_blank" rel="noreferrer">TVmaze</a> · CC BY-SA</span>}{providers.length>0&&<span>Streaming data by <a href="https://www.justwatch.com/in" target="_blank" rel="noreferrer">JustWatch</a>, via TMDB.</span>}</footer>
  </main>;
}

function providerType(value:string){return ({flatrate:"Subscription",free:"Free",ads:"Free with ads",rent:"Rent",buy:"Buy"} as Record<string,string>)[value]||value;}
function safeExternal(value?:string,allowed=["themoviedb.org","anilist.co","tvmaze.com"]){try{const url=new URL(value||"");return url.protocol==="https:"&&allowed.some(domain=>url.hostname===domain||url.hostname.endsWith(`.${domain}`))?url.toString():""}catch{return ""}}
