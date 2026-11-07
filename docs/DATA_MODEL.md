# Data model

SQLite remains the default and stores private data and normalized public catalogue data in separate tables.

| Table | Contents | Privacy |
| --- | --- | --- |
| `media_items` | User library, status, personal rating, notes, dates | Private local profile |
| `memories` | User-entered/imported context and explicitly sourced inferences | Private local profile |
| `taste_signals` | Dimension, value, direction, strength, confidence, source, evidence and confirmation time | Private local profile |
| `catalogue_items` | Provider-normalized titles, public metadata, IDs, poster/backdrop, ratings, detail JSON, timestamps | Public catalogue snapshot |
| `discovery_section_cache` | Provider, section IDs, fetch/expiry time, last refresh error | Public cache metadata |
| `recommendation_feedback` | Timestamped action, reason, temporary context and undo/library restoration state | Private interaction history |
| `research_sources` | Existing source-attributed web research records | Local app data |
| `schema_migrations` | Applied additive migration versions | Local app metadata |
| `app_settings` | Small local migration/seed markers | Local app metadata |

Catalogue rows are upserted by `(source_provider, provider_id)` and keep a separate source URL/external ID for explainability. Public records do not contain personal ratings or notes. Feedback events do not equate completion with enjoyment. User-facing rating remains separate from completion status.

## Taste provenance

`source=explicit` signals are entered/confirmed by the user. `source=inferred` signals are hypotheses generated from optional feedback reasons. Both store direction and strength/confidence; deleting or editing a signal is supported. Private taste state is never sent to public search providers.

## Backups and migrations

Use **Data → Download complete backup** to export portable JSON/CSV and restore with the existing merge/replace flow. Migrations only add fields/tables/indexes. The migration runner records each successful schema version in `schema_migrations` and preserves existing library and memory content.
