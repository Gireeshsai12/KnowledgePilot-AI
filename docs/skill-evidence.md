# Skill evidence

| Skill | Source | Executed check |
| --- | --- | --- |
| Typed FastAPI handlers, Pydantic validation, HTTP and OpenAPI | app.py | API suite and live HTTP smoke |
| SQLite schema initialization, constraints and atomic ingestion | schema.sql, app.py | Upload, deduplication and deletion |
| Password hashing, bearer sessions and role-based authorization | app.py | Sign-out, tenant isolation and viewer restrictions |
| PDF, DOCX, TXT, Markdown, CSV and HTML processing | retrieval.py | Format-specific integration tests |
| Section-aware chunking and overlap | retrieval.py | Unicode, chunk boundaries, page and heading citations |
| Sparse vectors, cosine similarity and reciprocal rank fusion | retrieval.py | All retrieval modes and toy precision@1 |
| Grounding, citations and abstention | retrieval.py, app.py | Source verification and out-of-corpus tests |
| Structured deterministic workflow | app.py | Two-document comparison with separately scoped citations |
| Responsive HTML, CSS, DOM rendering and HTTP client | static/ | JavaScript syntax, HTML/static route tests and Chromium smoke |
| Bash, PowerShell, Docker Compose and CI configuration | start.sh, start.ps1, compose.yaml, .github/workflows/verify.yml | Bash syntax and configuration parsing where available. Docker runtime, PowerShell and hosted CI were unexecuted. |
