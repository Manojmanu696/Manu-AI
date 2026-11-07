import { MediaItem, Recommendation } from "@/lib/api";

const tint: Record<string,string> = { movie:"#292a2c", anime:"#303033", tv:"#292a2c", game:"#303033", book:"#292a2c" };
export function MediaCard({ recommendation, item, onEdit }: { recommendation?:Recommendation; item?:MediaItem; onEdit?:(item:MediaItem)=>void }) {
 const content = recommendation?.item || item!; const color = tint[content.media_type] || "#292a2c";
 const fit = recommendation?.fit || (recommendation ? recommendation.score >= 74 ? "Excellent fit" : recommendation.score >= 63 ? "Strong match" : recommendation.score >= 52 ? "Good fit" : "Explore" : "");
 return <article className="media-card" onClick={()=>onEdit?.(content)}><div className="poster" style={{background:color}}>{content.image_url ? <img src={content.image_url} alt={`${content.title} poster`}/> : <><span className="poster-type">{content.media_type}</span><strong>{content.title.slice(0, 1)}</strong></>}</div><div className="card-copy">{recommendation && <span className="match">{fit}</span>}<h3>{content.title}</h3><p>{content.genres || "Uncategorized"}</p><div className="card-meta">{content.personal_rating ? <span className="rating">★ {content.personal_rating}</span> : <span>{content.release_year || "—"}</span>}<span>{content.runtime}</span></div>{recommendation && <p className="reason">{recommendation.reasons[0]}</p>}</div></article>
}
