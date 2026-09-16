# Data model

## Media item

`media_items` holds movies, anime, TV shows, games, and books. It includes the title, description, comma-separated genres/tags, 1–10 personal rating, like/dislike/neutral sentiment, status, notes, dates, optional external identifiers/URLs, poster URL, and optional AI metadata. Statuses are `want`, `current`, `completed`, `dropped`, and `on_hold`.

## Memory

`memories` holds a category, content, source, and optional confidence. `source=user` means the owner entered it; `source=inferred` means it is a non-permanent AI inference. The UI always separates them.

`is_demo` makes sample data removable without touching real data. SQLite is a documented, broadly portable relational format; the export format avoids requiring it by including JSON and CSV.

