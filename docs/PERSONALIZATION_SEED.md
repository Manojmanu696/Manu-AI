# Personalization and data integrity

Manu AI runs a FastAPI service against SQLite and serves the dashboard through Next.js. A new database starts with an empty personal profile. Archived demo rows remain available in a complete backup.

| Finding | Cause | Fix |
| --- | --- | --- |
| Sample ratings and tastes appeared in personal views. | Startup populated a sample profile and discovery and history queries mixed origins. | Personal queries gate on provenance. Demo writes through the application are disabled. |
| Edits reset unrelated fields or invented completion dates. | Generic updates wrote model defaults, and the review route initialized the status as completed. | Edits apply only submitted fields. Explicit status changes and checkpoints provide viewing evidence. Ratings have separate revision records. |
| Import could add duplicates, lose reference tables, or overwrite an existing rating. | The importer copied rows without reconciling identities and skipped three exported tables. | Merge uses namespaced provider IDs or an exact type, title and release-year match. It flags conflicts and restores catalogue references with remapped IDs. Replacement creates a backup first. |
| Approved memories could remain labeled as inferred. | The Bridge sent every approval as an inference and cleared the proposal even if saving failed. | The approval API records the user's authorization. It deduplicates proposals and commits an approval batch together. |
| Discovery rewarded completion and public ratings as personal taste. | Separate ranking implementations mixed activity, popularity and preference. | A shared heuristic considers curiosity, stakes, progression and payoff. Fresh recommendations filter activity and negative feedback, and vary genre and media type. |
| Missing provider information could read as proof of unavailability. | The public lookup used the same fallback for a failed request and an empty result. | Unverified availability, verified empty listings and confirmed provider offers have separate states. |

Rating revisions retain source, scale, precision and reason. Approximate and alternate-scale entries stay in history. Personal fit is a ranking signal. AI predictions and public ratings have separate labels. A viewing status of Unknown does not imply completion or viewing plans.

The Data screen can download portable JSON and ZIP, merge a backup, and list unresolved records. A full backup contains quarantined rows too. Live regional availability and audio are only confirmed when a data source reports them.
