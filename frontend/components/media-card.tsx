import { MediaItem, Recommendation } from "@/lib/api";
import { Icon } from "./icons";

const tint: Record<string,string> = { movie:"#9d72ff", anime:"#ff6b9d", tv:"#3cc9c5", game:"#efb941", book:"#75b86e" };
export function MediaCard({ recommendation, item, onEdit }: { recommendation?:Recommendation; item?:MediaItem; onEdit?:(item:MediaItem)=>void }) {
 const content = recommendation?.item || item!; const color = tint[content.media_type] || "#8aa0ff";
 return <article className="media-card" onClick={()=>onEdit?.(content)}><div className="poster" style={{background:`linear-gradient(145deg, ${color}40, #151822 64%)`}}>{content.image_url ? <img src={content.image_url} alt=""/> : <><span className="poster-type">{content.media_type}</span><strong>{content.title.slice(0, 1)}</strong></>}</div><div className="card-copy">{recommendation && <span className="match">{recommendation.score}% <em>match</em></span>}<h3>{content.title}</h3><p>{content.genres || "Uncategorized"}</p><div className="card-meta">{content.personal_rating ? <span className="rating">★ {content.personal_rating}</span> : <span>{content.release_year || "—"}</span>}<span>{content.runtime}</span></div>{recommendation && <p className="reason"><Icon name="sparkle" size={12}/>{recommendation.reasons[0]}</p>}</div></article>
}
