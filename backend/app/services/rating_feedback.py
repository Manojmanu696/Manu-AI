import re

from ..models import LocalAIRecord


def title_key(title):
    return (title.get("media_type"), " ".join((title.get("title") or "").casefold().split()), title.get("release_year"))


def extract_rating_feedback(message, title):
    if not title.get("title") or not title.get("media_type"):
        return None
    name = re.escape(title["title"])
    target = rf"(?:it|this (?:title|show|series|movie|film|anime)|{name})"
    score = r"(?:around\s+|about\s+)?(?:a\s+)?(10(?:\.0)?|[1-9](?:\.\d)?)(?:\s*/\s*10\b)?(?![\w%]|\.\d|\s*(?:[/–-]\s*\d|/|or\s+\d))"
    statement = r"(?:\bi(?:\s+would|['’]d)|(?:^|[.!]\s+)i)"
    pattern = rf"{statement}\s+(?:rate|give)\s+{target}\s+(?:at\s+)?{score}(?!\s*\?)"
    matches = re.findall(pattern, message, re.IGNORECASE)
    # Older voice-transcribed messages can say "read" when asking to update a score.
    if not matches and re.search(r"\bupdate\s+(?:your|the|my)\s+(?:score|rating)\b", message, re.IGNORECASE):
        matches = re.findall(rf"\bi\s+would\s+read\s+{target}\s+{score}", message, re.IGNORECASE)
    if len(matches) != 1:
        return None
    return {
        "score": float(matches[0]),
        **{key: title.get(key) for key in ("title", "media_type", "release_year", "genres")},
    }


def record_feedback(record):
    data = record.data
    if record.kind != "chat" or data.get("role") != "user":
        return None
    title = data.get("title")
    if not isinstance(title, dict) or not isinstance(title.get("title"), str):
        return None
    if "rating_feedback" not in data:
        return extract_rating_feedback(data["content"], title)
    rating = data["rating_feedback"]
    if isinstance(rating, dict) and type(rating.get("score")) in (int, float) and 1 <= rating["score"] <= 10:
        return {"score": rating["score"], **{key: title.get(key) for key in ("title", "media_type", "release_year", "genres")}}
    return None


def latest_feedback(db):
    feedback = {}
    records = db.query(LocalAIRecord).filter_by(kind="chat").order_by(
        LocalAIRecord.created_at.desc(), LocalAIRecord.id.desc()
    )
    for record in records:
        if rating := record_feedback(record):
            feedback.setdefault(title_key(rating), rating)
    return feedback
