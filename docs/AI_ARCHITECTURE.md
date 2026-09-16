# AI architecture

Before answering a question, the retrieval layer selects relevant library rows and memories from local data. It does not blindly serialize the complete database into every prompt.

The response contract separates `facts`, `recommendations`, and `assumptions`. This makes it clear which statements come from the owner's library and which are ranked suggestions or inferences.

`AIProvider` is provider-agnostic:

```
AIProvider
├── LocalProvider (implemented: private, deterministic v1 fallback)
├── OpenAIProvider (boundary prepared)
├── OllamaProvider (future local-model adapter)
├── AnthropicProvider (future adapter)
└── GoogleProvider (future adapter)
```

Cloud providers must be explicitly chosen in Settings and must use environment variables; keys are never written to the database or frontend code. A future Ollama adapter will use the same retrieved context and response schema.

