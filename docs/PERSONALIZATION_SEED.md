# Manu AI first-launch personalization

Manu AI uses a curated, non-sensitive seed profile so the first homepage is useful before the user has entered local ratings.

The seed is deliberately limited to stable preferences relevant to discovery and software-project behavior. It excludes sensitive personal/medical/financial information and does not pretend that inferred preferences are explicit facts.

Seed source: `backend/app/seed_profile.py`.

The seed should be inserted only when the local database has no user memories. Existing user data must never be overwritten.

Recommendation behavior:
- Explicit user preferences have highest weight.
- Ratings and feedback outrank generic popularity.
- Existing watchlist is surfaced and considered.
- Short, engaging, non-filler content is favored.
- Slow emotional drama is down-ranked unless the user explicitly asks for it.
- Current facts such as OTT availability, releases, prices, and recent content should use live web research when needed.
- Internet research is a source of public facts/candidates; it is not a replacement for private local memory.
