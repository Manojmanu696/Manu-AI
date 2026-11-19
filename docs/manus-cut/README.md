# Manu’s Cut redesign

The original and redesigned home and Memento title views were captured in Chromium at 1440 × 960 and 390 × 844 with the repository’s sample library. The original title view opened as a modal. The redesigned title has a shareable link and a journal.

| View | Before | After |
| --- | --- | --- |
| Desktop home | [Open screenshot](before-home-desktop.png) | [Open screenshot](after-home-desktop.png) |
| Desktop title | [Open screenshot](before-title-desktop.png) | [Open screenshot](after-title-desktop.png) |
| Mobile home | [Open screenshot](before-home-mobile.png) | [Open screenshot](after-home-mobile.png) |
| Mobile title | [Open screenshot](before-title-mobile.png) | [Open screenshot](after-title-mobile.png) |

## Verification

Desktop and mobile Chromium covered title search, saving and changing status, logging movie and series checkpoints, writing and editing a final review, revealing spoilers, and reloading. Verification included an existing series record and a title with missing artwork and credits. The production build and lint passed. Automated accessibility checks on home, Discover, and the title page found no WCAG A or AA violations at the tested sizes. The backend tests also cover journal backup and restore, catalogue and library identity, and region-specific provider handling with a simulated TMDB response.

## Integrations

- The app uses its existing single local profile and SQLite library. The checkout includes sample data. A personal library remains in its local database.
- Public search, current streaming availability, and live enrichment require the existing `TMDB_API_KEY` setting. Availability links go to the regional provider listing supplied by TMDB and JustWatch. Stored availability notes are labeled unverified. No live key was available during verification.
- Optional copyediting uses the existing local Ollama integration. The editor shows the suggestion for review and keeps manual writing available. No running model was available during verification.
- Sample artwork, trailers, and credits are sourced from [TMDB](https://www.themoviedb.org/). Existing library records are enriched through the available catalogue and provider data.
