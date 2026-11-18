# API guide

Interactive OpenAPI is available at /docs, with the schema at /openapi.json. Register with POST /api/register using email and password, then POST /api/login and send the returned token as Authorization: Bearer TOKEN. Sessions last one hour and POST /api/logout revokes the current session.

| Method and route | Purpose |
| --- | --- |
| GET /health | Verify SQLite connectivity |
| GET and POST /api/workspaces | List memberships or create a workspace |
| PUT /api/workspaces/{id}/members | Grant an existing account viewer or editor access |
| GET and POST /api/workspaces/{id}/documents | List documents or index a multipart file |
| DELETE /api/workspaces/{id}/documents/{document} | Remove a document and its chunks |
| POST /api/workspaces/{id}/demo | Load the included fictional data |
| GET /api/workspaces/{id}/search | Rank matches by query q, mode, document_id and top_k |
| POST /api/workspaces/{id}/chat | Create an extractive answer from question, optional document_id and top_k |
| POST /api/workspaces/{id}/chat/stream | Deliver excerpts and the final result as SSE events |
| GET /api/workspaces/{id}/history | Read the current user's recent questions |
| GET /api/workspaces/{id}/chunks/{chunk} | Open the citation source |
| POST /api/workspaces/{id}/compare | Compare first and second document IDs using a topic |

Duplicate uploads return the existing document ID with status duplicate. Indexed uploads return a chunk count. Unauthorized workspaces return 404. Authenticated members without the required role receive 403.
