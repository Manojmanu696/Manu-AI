# Discovery and recommendation engine

## Feed lifecycle

The home endpoint returns current SQLite snapshots immediately and schedules a background refresh when a section is missing or expired. Popular/trending, upcoming/release, and curated collections use separate cache intervals. Provider errors leave saved titles visible, record a last error, and use a short retry window. Manual refresh forces a worker run.

## Candidate retrieval and ranking

The adapters retrieve candidates from TMDB, AniList, TVmaze, and the local catalogue. Search candidates are normalized and persisted before the UI gets an item ID. Search merging removes repeated same-type title/year records.

The local rank stage uses:

- structured explicit/inferred taste signals with confidence and provenance;
- highly and poorly rated library items (rated thresholds only);
- repeated positive feedback on distinct titles;
- per-title love/like/not-interested actions;
- public rating with vote-count confidence weighting;
- mode, temporary mood and novelty signals;
- seen-title suppression and genre/franchise re-ranking.

Content similarity uses lexical overlap and an optional local Ollama sentence-embedding stage. `OLLAMA_EMBEDDING_MODEL` defaults to `all-minilm`; only loopback Ollama URLs are accepted. Embeddings are content-hash cached in SQLite, rebuilt after local text changes, and compared against highly rated local titles and positive taste signals. When Ollama is absent, the lexical and structured ranker keeps working. No private title history or taste memory is placed in TMDB, AniList, or TVmaze requests. Ranking labels are qualitative and not probability estimates.

## Feedback and correction

Actions include love, like, not interested, already watched, watchlist, started, completed, dropped, and a post-watch rating. Optional dislike reasons add a weak inferred signal only for the specific stated dimension. A dislike does not blacklist the title's genre. Feedback has an undo endpoint; when an action created or changed a linked library item, undo removes/restores that change as well.

## Offline evaluation

Backend tests use mocked responses and local SQLite. They cover provider normalization, transient rate-limit retry, additive migration preservation, completion-neutral behavior, feedback undo, offline embedding cache behavior, backup round trips, and reproducible ranking metrics. There is not yet enough owner-labelled feedback to estimate real-world Precision@K/Recall@K/NDCG@K or claim improved recommendation quality.
