# Public providers and attribution

| Provider | Data used | Authentication | Cache / behavior | Required attribution |
| --- | --- | --- | --- | --- |
| [TMDB](https://developer.themoviedb.org/docs) | Movie/TV discovery, trends, popular, releases, ratings, genres, posters, detail, credits, trailers, India watch providers | `TMDB_API_KEY` in backend `.env` | Section TTLs; detail/watch providers refreshed on title open after 12 hours; timeouts/retries/bounded concurrency | Display an approved logo and the TMDB notice; [TMDB FAQ](https://developer.themoviedb.org/docs/faq). Watch-provider data must credit JustWatch. |
| [AniList](https://docs.anilist.co/) | Popular/current-season anime and title search via GraphQL | None | Bounded concurrency and retry/backoff for 429/transient errors; normal feed cache | Link the source on the title detail page. Respect its [rate limits](https://docs.anilist.co/guide/rate-limiting). |
| [TVmaze](https://www.tvmaze.com/api) | Complementary TV catalogue and title search | None | Store feed snapshots for 24 hours; respect the API's response cache guidance and rate limit | Link TVmaze and retain CC BY-SA attribution per its [API plans](https://www.tvmaze.com/api/plans). |

The API key is read by FastAPI only. Provider adapters do not receive user memories, notes, personal ratings, or the full private watch history. Search terms typed by the user are sent to the selected public title provider, which is necessary for live title search.

TMDB watch-provider results are grouped by the returned category: subscription (`flatrate`), free, ad-supported, rental, and purchase. A provider is displayed only when returned for region `IN`; the linked TMDB page provides current deep links. No service availability is inferred from a title's country or studio.

## Troubleshooting

- `/providers/health` reports reachability and missing TMDB key state.
- Missing TMDB key leaves AniList and TVmaze usable.
- A temporary outage keeps prior SQLite cache rows visible and surfaces the failure time/message.
- Never add real keys to `.env.example`, source code, browser `NEXT_PUBLIC_*` variables, logs, or commits.
