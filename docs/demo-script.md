# Demo video script

A 3–4 minute walkthrough that takes a viewer from "what is this" to "I
believe it works" without padding. Record once with a clean voice
recording, edit minimally.

## Setup before recording

- Run `make clean && make up && make migrate && make eval-seed` so
  every container is fresh and the sample documents are indexed.
- Open three browser tabs in a private window:
  1. <http://localhost:5173/chat>
  2. <http://localhost:5173/documents>
  3. <http://localhost:9001> (MinIO console — log in with
     `minioadmin` / `minioadmin`)
- Open a Terminal tab in the project directory.
- Set OS notifications to "Do Not Disturb."
- Use a screen recorder that captures system audio (Loom, OBS, QuickTime).

## Outline (3 min 30 sec)

### 0:00 – 0:20 — Opening
*[Static title screen or system-architecture.png as a freeze frame]*

> "This is a retrieval-augmented question-answering system for internal
> documents. Users upload policies and SOPs, ask questions in plain
> language, and get answers grounded in their own corpus with inline
> citations. Three minutes; let me show you."

### 0:20 – 0:50 — The problem and the architecture
*[Show docs/images/system-architecture.png on screen]*

> "Internal docs are scattered across SharePoint, Confluence, shared
> drives. Generic LLMs can't see them and hallucinate when they don't
> know. This system runs entirely against the user's own corpus.
>
> The shape: a React SPA, a FastAPI backend, Postgres with the pgvector
> extension for semantic search, MinIO standing in for S3 in local
> dev, and Bedrock for the chat LLM."

### 0:50 – 1:30 — Documents page
*[Switch to /documents]*

> "Here's the documents view. I'll drag in an employee handbook."

*[Drag a file in. Wait for the indexed badge.]*

> "The pipeline parses the PDF, splits it into 800-token chunks with
> 100-token overlap, embeds each chunk into a 1024-dimension vector
> using BAAI's bge-large model running locally on the API host, and
> stores both the text and the vector in Postgres. End to end, that
> took about three seconds for a five-page document."

*[Switch to MinIO console, click into the bucket, show the actual
uploaded file.]*

> "The raw bytes land in object storage — MinIO locally, real S3 in
> production via a single config swap."

### 1:30 – 2:30 — Chat
*[Switch to /chat]*

> "Now the chat side. I'll ask a question that's answered in the
> handbook."

*[Type "What is the PTO policy?", send. Let it stream.]*

> "Notice three things. First, tokens are streaming in via Server-Sent
> Events; the user sees the answer as the model generates it. Second,
> there are numbered citation chips inline. Third — and this is the
> part most demos skip — the right-hand panel shows the actual source
> snippet, the document filename, and the page number."

*[Click into a citation; read the snippet aloud.]*

> "Now I'll ask something the corpus doesn't cover."

*[Type "What's the company stock ticker?", send.]*

> "The system is prompted to abstain when retrieved context is
> insufficient. It returns the abstention sentence instead of guessing.
> That behavior is enforced by the system prompt and validated by an
> evaluation harness."

### 2:30 – 3:10 — Evaluation
*[Switch to Terminal. Run `make eval LABEL=demo`.]*

> "The eval harness has 20 hand-written questions — 15 factual lookups
> with expected sources and keywords, 5 explicitly out-of-scope
> abstention questions. Let me run it live."

*[Wait for the run to finish; let the summary scroll past.]*

> "On this run: 100% citation accuracy, 100% abstention precision, 98%
> keyword recall, p95 latency under two seconds. These numbers are
> reproducible and live in `evals/reports/` after every run."

### 3:10 – 3:30 — Close
*[Show the README on the GitHub page.]*

> "The repo has architecture diagrams, deployment notes, a security
> threat model, and a cost analysis at the documented usage tiers.
> Link in the description. Thanks for watching."

## Recording tips

- Speak slower than feels natural. The brain processes a demo at
  about 70% of normal speech speed.
- Pause for one beat after every transition between tabs.
- Edit out any stutters or "ums" — the few seconds you save make the
  whole video feel more confident.
- Don't apologize on camera. If a take goes wrong, re-record the
  segment and cut it in.
- Captions are non-optional. YouTube auto-generates them; on Loom
  enable the AI captions feature.
