"use client";
import {useEffect,useMemo,useState} from "react";
import {API_URL} from "@/lib/api";

type Memory={id:number;category:string;content:string;source:string;confidence:number|null};
export default function ProfilePage(){
 const [memories,setMemories]=useState<Memory[]>([]); const [loading,setLoading]=useState(true);
 const load=()=>fetch(`${API_URL}/memories`).then(r=>r.json()).then(setMemories).finally(()=>setLoading(false));
 useEffect(load,[]);
 const groups=useMemo(()=>memories.reduce<Record<string,Memory[]>>((a,m)=>(a[m.category]??=[]).push(m),{}),[memories]);
 const remove=async(id:number)=>{await fetch(`${API_URL}/memories/${id}`,{method:"DELETE"});load()};
 const confidence=(m:Memory)=>m.confidence==null?null:Math.round(m.confidence*100);
 return <main style={{maxWidth:1100,margin:"0 auto",padding:"56px 28px",fontFamily:"system-ui"}}>
  <a href="/">← Manu AI</a><p style={{letterSpacing:2,opacity:.6,marginTop:50}}>PERSONAL INTELLIGENCE</p><h1 style={{fontSize:52,margin:"8px 0"}}>What Manu knows <em>about you.</em></h1><p style={{fontSize:18,opacity:.7,maxWidth:720}}>A transparent profile of the information your local AI uses. User-provided context is separated from AI-inferred hypotheses.</p>
  {loading?<p>Loading your local profile…</p>:<>
   <div style={{display:"flex",gap:12,margin:"30px 0",flexWrap:"wrap"}}><b>{memories.length} memory signals</b><span>•</span><span>{memories.filter(m=>m.source==="inferred").length} inferred</span><span>•</span><span>{memories.filter(m=>m.source!=="inferred").length} explicit/imported</span></div>
   {Object.entries(groups).map(([category,list])=><section key={category} style={{margin:"28px 0",padding:24,border:"1px solid #ddd",borderRadius:18}}><h2 style={{textTransform:"capitalize"}}>{category.replaceAll("_"," ")}</h2>{list.map(m=><article key={m.id} style={{padding:"14px 0",borderTop:"1px solid #eee"}}><div style={{display:"flex",justifyContent:"space-between",gap:20}}><span>{m.content}</span><button onClick={()=>remove(m.id)}>Remove</button></div><small style={{opacity:.6}}>{m.source} {confidence(m)!=null?`• ${confidence(m)}% confidence`:""}{m.source==="inferred"?" • hypothesis":""}</small></article>)}</section>)}
   {!memories.length&&<section style={{padding:32,border:"1px dashed #aaa",borderRadius:18}}>Your profile is empty. Use <a href="/memory-bridge">ChatGPT Bridge</a> to teach Manu AI.</section>}
  </>}
 </main>
}
