# Future roadmap

## Near term

- Explicit provider settings and OpenAI/Ollama adapters
- External catalog/discovery adapters with provider-normalized candidates
- Better filters, image caching, and user-authenticated multi-profile support

## Integrations

Google Drive backup will live behind a `BackupProvider` interface and require OAuth consent. Official WhatsApp/API support will live behind a messaging adapter; no unofficial browser automation is planned.

## Agents and web research

A Browser/Research agent will perform search, page extraction, and structured candidate generation. A Recommendation agent will rank those candidates against local preferences. Each agent will have narrow permissions, clear provenance, and an approval boundary before consequential actions.

