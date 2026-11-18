# Architecture

The static dashboard calls the FastAPI REST API on the same origin. Each protected request resolves an expiring bearer session, then applies a workspace membership check. Owners grant access to registered accounts. Editors index and delete documents. Viewers can search and read. Query candidates are selected by workspace before ranking or source display.

Upload → parse into sections → split into overlapping chunks → atomically persist document and chunks in SQLite. The database stores the original upload for the lifetime of the document. Content hashes deduplicate uploads inside a workspace, and deleting a document cascades to the indexed chunks.

Question → filter accessible chunks → rank → select verbatim sentences → return citations. Keyword ranking uses logarithmic term frequency. Vector ranking fits sparse TF-IDF features to authorized candidate chunks and scores them using cosine similarity. Hybrid ranking uses reciprocal rank fusion with constant 60. Excerpts need one or two overlapping query terms, depending on query length. This heuristic can miss paraphrases and can surface passages that share terms without answering the question. Always inspect the citation. The small evaluation measures basic behavior on the included data.

Comparison runs the same extraction independently for two selected documents. Its structured result contains separate cited excerpts for each document. The backend exposes SSE events for the already computed result. The dashboard uses the JSON response. History is stored per account and workspace. Existing history can retain excerpts after a document is deleted, and opening its source will then return 404.

## Scope and deployment

This implementation is a single-node, trusted-local portfolio app. It uses SQLite, sparse lexical vectors and extractive answers. It implements synchronous ingestion, workspace-level roles and a deterministic comparison workflow. The requested PostgreSQL/pgvector and HNSW stack, neural embeddings, LLM/Ollama integration, prompt suite, autonomous agent/tool registry, Redis and background queues, React/TypeScript, JWT refresh/OAuth, organization and team hierarchies, cloud deployment and production observability remain outside this implementation. No production security or scaling certification was performed.

File parsers run in-process. Upload and extraction checks constrain ordinary inputs, but production ingestion of hostile files would need isolated workers, memory/time quotas and additional hardening. Local registration has no email verification or rate limiting. Bearer tokens are stored in browser session storage and only their hashes are saved in SQLite. Use the app on loopback with trusted local users and uploads.
