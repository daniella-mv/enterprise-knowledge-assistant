# API reference

Auto-generated OpenAPI is available at <http://localhost:8000/docs>
when the stack is running. This page summarizes the routes for quick
reference.

## Health

### `GET /health`

Liveness probe.

**Response 200**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "local"
}
```

Every response also carries an `X-Request-Id` header echoing the id
bound to the structlog context for that request.

## Documents

### `POST /api/documents`

Upload + ingest a document. Multipart form upload with a single
`file` part.

**Request**

```
Content-Type: multipart/form-data
file: <bytes>
```

Supported MIME types: `application/pdf`,
`application/vnd.openxmlformats-officedocument.wordprocessingml.document`
(DOCX), `text/plain`, `text/markdown`. Format is also detected from
the filename extension if the content type is generic.

**Response 201**

```json
{
  "id": "uuid",
  "filename": "handbook.pdf",
  "status": "indexed",
  "chunk_count": 8,
  "file_size": 24531,
  "mime_type": "application/pdf",
  "error": null,
  "created_at": "2026-05-06T01:23:45Z",
  "indexed_at": "2026-05-06T01:23:48Z"
}
```

If parsing/chunking/embedding fails, the response is still 201 with
`status: "failed"` and a populated `error` field.

### `GET /api/documents`

List the requesting user's documents, most recent first.

**Response 200**

```json
{
  "items": [ /* Document objects */ ],
  "total": 3
}
```

### `GET /api/documents/{id}`

Fetch a single document. Returns 404 if the id doesn't exist or
belongs to another user.

### `DELETE /api/documents/{id}`

Remove the document from object storage and the database. Chunks are
cascaded by the foreign key. Returns 204 on success, 404 otherwise.

## Chat

### `POST /api/chat`

Server-Sent Events stream. The body is JSON.

**Request**

```json
{
  "message": "What is the PTO policy?",
  "top_k": 5
}
```

`top_k` is optional, default 5, range 1–20.

**Response 200, content-type `text/event-stream`**

```
event: token
data: Employees

event: token
data:  receive 15 PTO days

event: token
data:  per year [c_0].

event: done
data: {"citations": [{"short_id": "c_0", "chunk_id": "...", "document_id": "...", "document_filename": "handbook.md", "page": 1, "snippet": "...", "score": 0.016}]}
```

If Bedrock fails:

```
event: error
data: {"message": "ThrottlingException: ..."}
```

The HTTP status remains 200 — errors are streamed inline so the
frontend can render a partial answer alongside the failure message.

## Errors

All non-streaming errors share this envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "document not found"
  }
}
```

Codes are stable strings:

| Code                | Status | Meaning                                  |
|---------------------|--------|------------------------------------------|
| `internal_error`    | 500    | Unexpected server error                  |
| `not_found`         | 404    | Resource doesn't exist or isn't visible  |
| `unauthorized`      | 401    | (reserved; not yet emitted in v1)        |
| `ingestion_error`   | 500    | Parse/chunk/embed pipeline failure       |
| `retrieval_error`   | 500    | Vector or keyword query failed           |
| `generation_error`  | 502    | Upstream LLM unavailable                 |
| `storage_error`     | 502    | Object storage unreachable               |

Pydantic validation errors (e.g. missing required fields) come back
with FastAPI's default 422 envelope, not the custom one above.
