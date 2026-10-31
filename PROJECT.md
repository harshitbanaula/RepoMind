# RepoMind Project Guide

## Evidence and scope

This guide describes the tracked repository at branch `feature/mcp-servers`, commit `da3cc7d`, and incorporates the supplied Phase 4-8 roadmap. Repository history confirms Phases 1-3 as implemented. Phases 4-8 are plans, not existing code. Product and deployment decisions in those future phases must be verified before implementation where noted.

## Project overview

RepoMind is a Python backend for repository-aware code assistance. It connects GitHub repositories, clones and indexes their source, retrieves relevant code with lexical and vector search, and streams LLM answers with citations. It also has standalone MCP servers for GitHub pull-request operations and repository search. The planned next step is a LangGraph agent that combines these capabilities, followed by HTTP/SSE integration, authentication, frontend, and evaluation.

### Requirements evidenced by current code

- HTTP health, repository connect/list/status, and question-answering routes.
- Per-user repository ownership and search scoping.
- Source filtering/chunking, BM25 and vector retrieval, and streamed Groq answers with citations.
- MCP tools to read a PR diff, post an inline review comment, and search indexed repository code.
- PostgreSQL, Redis, and Qdrant services configured through Docker Compose.

These are inferred from implementation and tests; no independent product requirements specification is tracked.

## Repository structure

| Path | Responsibility |
|---|---|
| `backend/app/main.py` | FastAPI application and route registration. |
| `backend/app/api/` | Health, repository, and streaming ask endpoints; current-user dependency. |
| `backend/app/core/` | Settings, database session, logging, and Fernet token encryption helpers. |
| `backend/app/models/` | SQLAlchemy `User` and `Repo` models and shared base. |
| `backend/app/schemas/` | Pydantic request/response models. |
| `backend/app/rag/` | GitHub API access, cloning, source filtering/chunking, embeddings, Qdrant/BM25 indexing, and hybrid retrieval. |
| `backend/app/mcp_servers/` | Standalone GitHub and repository-search MCP servers. |
| `backend/app/mcp_client/` | MCP server connection and tool-loading cache. |
| `backend/alembic/` | Database migration environment and initial schema migration. |
| `backend/tests/` | Tests for ask streaming, chunking, MCP behavior, and retrieval ranking. |
| `backend/requirements.txt` | Python application and test dependencies. |
| `backend/Dockerfile`, `docker-compose.yml` | Container image and local service topology. |
| `.env.example` | Environment variable template. |

There is no tracked frontend, OAuth route, LangGraph agent, review API, webhook endpoint, or API invocation of the MCP tools.

## Completed phases

### Phase 1 - Backend foundation

**Evidence:** Initial project commit `219925b` (2026-10-11).

- Created the FastAPI application and health endpoint.
- Added settings, async SQLAlchemy database setup, structured logging, and Fernet token encryption/decryption helpers.
- Defined `User` and `Repo` persistence models, including a unique per-user repository constraint and cascading relationship.
- Added the initial Alembic migration.
- Added Docker Compose services for the API, PostgreSQL, Redis, and Qdrant, plus a Python 3.11 backend image.

**Boundary:** Authentication flows and user provisioning are not implemented; later endpoints expect persisted users.

### Phase 2 - Repository ingestion and hybrid RAG

**Evidence:** Commit `e90811e` (2026-10-20).

- Added repository connect/list/status endpoints. Connect validates repository metadata and schedules in-process background indexing.
- Implemented shallow GitHub clone/fetch, source file exclusions and size limits, language detection, Python AST-aware chunking, and line-window fallback chunking.
- Added FastEmbed embeddings, Qdrant vector storage, and a per-user/per-repository local BM25 index.
- Implemented reciprocal-rank fusion for hybrid search.
- Added `POST /ask`: checks ownership and index readiness, retrieves context, streams Groq tokens over SSE, and returns source citations.
- Added tests for chunking, retrieval fusion, and ask-stream events.

**Boundary:** `X-Dev-User` supplies a numeric GitHub ID as a development identity shim. Indexing uses FastAPI background tasks; Redis is configured but not used as a queue.

### Phase 3 - MCP tools and host client

**Evidence:** Commit `da3cc7d` (2026-10-26), branch `feature/mcp-servers`.

- Added GitHub MCP tools `get_diff` and `post_review_comment`.
- Added repository-search MCP tool `search_code`, scoped by user.
- Added an MCP client that loads each server independently and caches available tools/connection status.
- Added tests for structured GitHub errors, empty comment rejection, repository-not-ready handling, and unavailable MCP servers.

**Boundary:** MCP tools and a client loader exist, but no API or agent calls `load_tools()` or conducts an end-to-end review. The GitHub server currently takes a token as a tool argument; the supplied plan places its secure transport migration in Phase 5.

## Current status

**Latest implemented phase: Phase 3.** Phase 4 has not started. The next work is the LangGraph agent layer, not a new HTTP route.

- Current routes: `/health`, `/repos`, `/repos/{repo_id}/status`, and `/ask`.
- Current-user dependency uses `X-Dev-User`; GitHub OAuth settings exist, but OAuth routes/callback are absent.
- `/ask` calls Groq directly; MCP tools are not currently exposed to an agent.
- No review orchestration, graph interrupt/resume, review API, comment approval flow, or webhook exists.
- `Repo` has no `indexed_sha` field yet.
- Existing tests cover selected units and endpoint behavior, not end-to-end provider, OAuth, deployment, or full workflow behavior.
- `frontend/` is absent; `.gitignore` mentions a future frontend environment file.

## Remaining phases

Phase definitions below follow the supplied roadmap. Phases 4-8 are targets, not claims about current implementation.

### Phase 4 - LangGraph agent (graph only; no HTTP changes)

**Objective:** Implement ask and PR-review agent graphs as internal backend capabilities. Phase 4 does not add/change HTTP routes, post GitHub comments, or migrate the GitHub MCP transport.

#### 4.1 Version and checkpointer audit (first task)

1. Inspect available/resolvable versions of `langgraph` and `langgraph-checkpoint-postgres`; the current requirements list them without pins.
2. Select a compatible pair and pin exact compatible versions in `backend/requirements.txt`.
3. Verify `interrupt()`/`Command(resume=...)`, `astream_events` v2, and `AsyncPostgresSaver` setup/resume semantics against those versions. Do not rely on behavior from a different LangGraph major version.
4. Verify the checkpointer schema/setup against PostgreSQL. If a database migration is needed, derive it from the selected checkpointer package's schema rather than hand-authoring an assumed version-specific schema.

#### 4.2 Deliverables

| Deliverable | Responsibility |
|---|---|
| `backend/app/agents/state.py` | `AgentState` TypedDict: `user_id`, `repo_id`, `thread_id`, `mode`, `input`, `messages`, `context`, `draft`, `critique`, `retries`, `final`, `review_comments`, `low_confidence`. Use an appropriate message reducer. **No token field.** |
| `backend/app/agents/nodes.py` | Router, retriever, agent, critic, and finalize nodes plus deterministic validation. |
| `backend/app/agents/graph.py` | Graph assembly, ask/review edges, retry path, and review interrupt. |
| `backend/app/agents/checkpointer.py` | `AsyncPostgresSaver` lifecycle and supported idempotent setup. |
| `backend/app/agents/runner.py` | `run_ask`, `run_review`, `resume_review`, and typed `astream_events` v2 helper. Internal runner only; not HTTP. |
| `Repo.indexed_sha` and migration | Persist the commit SHA actually indexed for a repository. |
| Indexer update | After clone/fetch, run `git rev-parse HEAD` and store that SHA with the index metadata. |
| Tests | Direct runner/graph tests with mocked LLM, MCP, and checkpoint behavior; no HTTP tests required for Phase 4. |

#### 4.3 Node and graph behavior

1. **Router:** Classify ask vs review only when `mode` was not already supplied. If mode is known, bypass model classification.
2. **Retriever:** Use hybrid retrieval scoped by `user_id` and `repo_id`. Review mode should use changed files in the diff to guide context retrieval.
3. **Agent:** Use configured Groq model and MCP tools as graph capabilities. The Phase 3 `get_diff(owner, repo, pr_number, token)` signature remains unchanged during Phase 4. Tests use a placeholder token and mocked tools; this is test scaffolding, not production credential guidance. Moving credentials outside model-visible tool arguments is Phase 5.
4. **Critic:** Use structured output, e.g. Pydantic `CriticOutput(passed, critique, low_confidence)`, and verify the selected Groq model supports the chosen structured-output method. Limit retries to one.
5. **Finalize:** Perform deterministic, zero-LLM validation:
   - For each citation in `final`, require `(path, start_line, end_line)` to exist in `state.context`. Drop ungrounded citations and mark `low_confidence=True`.
   - For every review comment, require `(path, line)` to match an added (`+`) line parsed from the diff. Drop invalid locations.
6. **Review graph:** Pause at `interrupt()` before final review completion. `run_review` returns `thread_id` and pending state; it does not post anything to GitHub. `resume_review` exercises the chosen LangGraph resume semantics from the runner/tests, not an HTTP endpoint.
7. **Ask runner:** Preserve the expected Phase 2 ask event sequence through the internal runner so Phase 5 can expose a compatible SSE stream.

#### 4.4 Implementation order

1. Finish version/checkpointer compatibility audit and pin dependencies.
2. Add `indexed_sha` to model and migration; update indexer to persist the fetched commit SHA.
3. Define state and structured critic output; test the types and validation helpers.
4. Implement router/retriever/agent/critic/finalize nodes.
5. Assemble graph, one-retry path, review interrupt, and checkpointer lifecycle.
6. Implement runner functions and typed event helper.
7. Add mocked tests, run focused tests and full backend suite, and document dependency/version decisions.

#### 4.5 Tests and exit criteria

- Ask runner emits the expected event sequence; LLM and MCP are mocked.
- Review runner pauses at interrupt and exposes resumable `thread_id`/pending state; test resume semantics with the pinned LangGraph version.
- Critic retries at most once.
- A fabricated citation missing from context is dropped and lowers confidence.
- A fabricated comment on a line not added in the diff is dropped.
- No test needs live GitHub, Groq, or Qdrant credentials. No HTTP route or GitHub comment post is added.
- Migration/indexing tests prove `indexed_sha` persistence.
- Focused and full backend tests pass.

**Phase 4 is done when** the ask runner streams the agreed events, review pauses/resumes in tests, critic retry is bounded, deterministic validators work, indexed SHA is saved, and there are no `backend/app/api/` changes or GitHub writes in the phase.

### Phase 5 - HTTP/SSE integration, approval, and webhook

**Objective:** Expose Phase 4 runners through HTTP, enforce thread ownership, handle GitHub credentials safely, and connect explicit human approval to comment posting.

#### 5.1 Secure GitHub MCP transport

- Migrate `github_server` from stdio to streamable HTTP.
- Remove `token` from `get_diff` and `post_review_comment` tool signatures.
- Pass the user's credential in the MCP HTTP `Authorization` header, not tool arguments, model tool-call messages, or tool-call logs.
- Repo search may remain stdio while it remains credential-free.
- Test transport authentication and prove credentials do not enter model-visible schemas, logs, or outputs.

#### 5.2 API, state, and workflow

1. Add a `threads` table with `thread_id`, `user_id`, `repo_id`, `mode`, `status`, and `created_at` (plus only fields needed by the selected checkpoint design).
2. Enforce ownership with a database query constrained by both `thread_id` and `user_id`; never infer ownership by parsing an ID prefix.
3. Add `POST /review` to verify repository access, call `runner.run_review`, persist thread ownership/state, and return a thread ID.
4. Add `POST /review/{thread_id}/resume` to verify ownership, receive explicit approval and edited/selected comments, and resume the graph. Only after approval, post comments through the authenticated streamable-HTTP MCP client. Report per-comment success/failure.
5. Add `GET /ask/{thread_id}/stream` and `GET /review/{thread_id}/stream` (or documented equivalent) as SSE adapters over `runner.astream_events`; verify ownership before streaming.
6. Define API error and event shapes. Do not represent tool/provider failure as successful review output.

#### 5.3 Webhook and operational controls

- Verify `X-Hub-Signature-256` using HMAC and constant-time comparison.
- Add `webhook_deliveries` keyed by delivery UUID/ID. Deduplicate deliveries atomically; duplicate delivery returns success without rerunning the review.
- Resolve connected repositories by canonical `repository.full_name`. Unknown repo is a no-op (planned `202`).
- Start review as the connected repository owner's identity/token, not the webhook sender's identity.
- Webhook reviews pause for human approval and never post automatically.
- Add Redis per-user rate limiting, request-ID middleware, and separate liveness/readiness endpoints. Readiness checks required DB, Redis, and Qdrant connectivity.

#### 5.4 Tests and exit criteria

- Only the owning user can view/resume a thread.
- Duplicate delivery IDs do not launch duplicate reviews.
- Invalid webhook signatures are rejected; unknown repositories are no-op.
- A webhook/manual review pauses pending approval; unapproved reviews never post.
- Approved flow posts only selected/edited comments and reports each result.
- Credential is not model-visible.
- SSE, rate limit `429`/TTL recovery, request IDs, liveness, and readiness are tested.

### Phase 6 - GitHub OAuth and session authentication

**Objective:** Replace `X-Dev-User` with validated authentication while preserving Phase 5 repository/thread ownership.

#### Decision document before code

Write `docs/auth-decision.md` and choose a deployment/cookie model:

- **Model A (recommended in supplied plan):** Same-origin reverse proxy, such as Next.js rewriting `/api/*` to backend. Browser sees one origin; configure a secure HTTP-only cookie with suitable `SameSite=Lax`.
- **Model B:** Cross-site frontend and API. Requires `SameSite=None; Secure`, credentialed fetches, exact CORS origins with credentials, and CSRF protection (e.g. double-submit token).

Document chosen model, cookie attributes, CORS/proxy, CSRF, local development, and deployment consequences before implementation.

#### Implementation and completion criteria

- Use a GitHub OAuth App as the supplied plan specifies; document scopes (proposed `read:user`, `repo`) and trade-offs.
- Implement `/auth/github/login`, `/auth/github/callback`, state validation, identity lookup/upsert, encrypted provider-token storage, and JWT session in an HTTP-only cookie.
- Treat JWT session refresh separately from GitHub OAuth token refresh. The supplied plan assumes OAuth App tokens do not expire unless revoked; verify actual app/provider settings and do not invent a GitHub token-refresh flow.
- Replace `X-Dev-User` on protected routes; explicitly identify public auth routes and signed webhook route.
- Add tests for OAuth errors, state validation, invalid/expired JWT, identity mapping, and cross-user repo/thread/search access.
- Verify OAuth round-trip in a real browser under the selected cookie model. No protected route works without valid authentication; secrets remain encrypted and server-side.

### Phase 7 - Frontend

**Objective:** Build a browser application against Phase 5 APIs and the Phase 6 cookie decision. No frontend code is currently tracked.

- Select and document frontend stack and typed API contract.
- Implement login, connected repositories, indexing status, Q&A, and PR review pages.
- Add typed SSE client/hook with reconnect and cleanup; display streamed answer, citations, review state, and errors.
- Construct source links with `repos.indexed_sha`, e.g. `github.com/{owner}/{repo}/blob/{sha}/{path}#L{start}-L{end}`, so links target indexed code.
- Support finding preview/edit/selection, explicit approval, and per-comment outcomes; opening a review must not write to GitHub.
- Follow selected same-origin proxy or cross-site CORS/CSRF model. Keep provider credentials server-side.
- Add frontend tests and build/type-check.

**Phase 7 is done when** a browser user can log in, connect/index a repo, ask and see streamed answers with working links, review a PR, edit/select findings, approve, and see comment outcomes.

### Phase 8 - Evaluation and release

**Objective:** Measure quality and operational behavior, document decisions, and prepare reproducible deployment. This phase measures quality; deterministic citation/comment validation remains Phase 4 behavior.

- Create an evaluation script (proposed `scripts/eval.py`) and a documented evaluation set.
- Score comment relevance with and without critic using a manual 0-3 rubric for groundedness, actionability, and avoiding nitpicks.
- Report MCP tool success rate, p50/p95 latency excluding human interrupt wait time, and counts of dropped citations/comments.
- Document architecture, setup, environment variables, demo flow, evaluation results, and LangGraph version in README.
- Verify deployment procedure (proposed Docker Compose on VPS/managed host plus Vercel frontend) matches the Phase 6 cookie decision.
- Verify setup from a fresh clone and document secret/configuration requirements.

**Phase 8 is done when** evaluation results are reproducible and reported without unsupported claims, dropped citation/comment counts are measured, and fresh-clone setup, migrations, tests/builds, and deployment steps are verified.

## Development roadmap

1. **Baseline:** From `backend`, run `python -m pytest` and record existing failures. Ensure PostgreSQL is available for checkpointer verification.
2. **Phase 4 version audit:** Resolve and pin compatible LangGraph/checkpointer packages; verify interrupt/resume, event streaming, and checkpointer setup before node implementation.
3. **Phase 4 graph:** Add state, nodes, graph, checkpointer, runners, `indexed_sha`, migration, deterministic validators, and mocked direct-runner tests. No API changes or GitHub writes.
4. **Phase 4 exit gate:** Verify ask event compatibility, review interrupt/resume, one retry maximum, citation/line validation, indexed SHA persistence, and full test suite.
5. **Phase 5 HTTP boundary:** Secure MCP transport; add owned threads, review start/resume and SSE, explicit approval/posting, signed/deduplicated webhook, rate limits, request IDs, readiness, and tests.
6. **Phase 6 auth:** Write cookie decision first, then OAuth/JWT; replace development header and prove cross-user isolation.
7. **Phase 7 frontend:** Implement user flows against the authenticated API and selected cookie architecture.
8. **Phase 8 evaluation/release:** Run documented evaluation, verify fresh-clone setup and deployment, and publish accurate architecture/configuration/results.

## Local validation reference

```powershell
docker compose up --build

Set-Location backend
python -m pytest
```

The API container applies Alembic migrations before starting Uvicorn. The sample environment contains placeholders; configure real local values before expecting database, GitHub, Groq, or Qdrant-backed operations to work. Phase 4 graph tests should mock LLM/MCP calls; PostgreSQL is needed to verify persistent checkpoint behavior.
