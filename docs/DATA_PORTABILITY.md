# Data portability

Manu AI backup files use the stable `manu-ai-portable-data` JSON envelope, currently version `1.0`.

Each backup ZIP contains:

- `manu-ai-data.json`: complete reconstruction data, including media, memories, statuses, ratings, dates, and demo markers.
- `media-items.csv` and `memories.csv`: readable tabular exports.
- `README.txt`: format identifier and restore note.

Import accepts either the ZIP or the JSON file. The UI offers a merge mode and a replace mode; replacement is explicit and never silent. Automated cloud backup is deliberately absent. For current Google Drive use, save the downloaded ZIP in a Drive-synced folder.

