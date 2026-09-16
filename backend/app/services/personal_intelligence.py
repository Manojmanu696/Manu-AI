from sqlalchemy.orm import Session
from ..models import Memory, MediaItem

POSITIVE = ("love", "loved", "like", "liked", "enjoy", "favorite", "favourite", "prefer", "best", "great")
NEGATIVE = ("hate", "hated", "dislike", "disliked", "boring", "slow", "avoid", "never")

def build_profile(db: Session):
    memories = db.query(Memory).order_by(Memory.created_at.desc()).all()
    explicit = [m for m in memories if m.source != "inferred"]
    inferred = [m for m in memories if m.source == "inferred"]
    themes = {}
    for m in memories:
        themes[m.category] = themes.get(m.category, 0) + 1
    positives = [m.content for m in memories if any(w in (m.content or '').lower().split() for w in POSITIVE)]
    negatives = [m.content for m in memories if any(w in (m.content or '').lower().split() for w in NEGATIVE)]
    return {
        "memory_count": len(memories),
        "explicit_count": len(explicit),
        "inferred_count": len(inferred),
        "themes": sorted([{"category": k, "signals": v} for k,v in themes.items()], key=lambda x:x["signals"], reverse=True),
        "positive_signals": positives[:30],
        "negative_signals": negatives[:30],
        "recent_memories": [{"id":m.id,"category":m.category,"content":m.content,"source":m.source,"confidence":m.confidence} for m in memories[:30]],
    }
