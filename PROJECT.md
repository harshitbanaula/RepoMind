# RepoMind Project Guide

## Evidence and scope

This guide describes the tracked repository at the `feature/mcp-servers` branch tip (`da3cc7d`). The commit history records three implementation increments. The source also refers explicitly to Phase 6 (replacing the development-user shim) and Phase 7 (frontend-related ignore rules), but does not contain a formal phase plan. Accordingly, Phases 4 and 5 below are recommended from the current code, and Phase 6 and 7 are described only to the extent supported by repository evidence. Proposed work is not presented as already approved or implemented.

## Project overview

RepoMind is a Python backend for repository-aware code assistance. It can connect a GitHub repository, clone and index its source, retrieve relevant code using lexical and vector search, and stream answers with source citations. It also exposes GitHub pull-request tools and repository search as MCP servers, providing the building blocks for an agent-assisted code-review workflow.

### Current implementation requirements

- Serve an HTTP API with health, repository connection/status, and question-answering routes.
- Associate repositories with users and scope repository access/search by user.
- Retrieve code context with hybrid BM25 and vector search.
- Stream generated answers and return file/line citations.
- Provide MCP tools for reading a pull-request diff, posting an inline review comment, and searching indexed repository code.
- Run the backend with PostgreSQL, Redis, and Qdrant services through Docker Compose.

These are requirements evidenced by existing implementation, dependencies, configuration, and tests; no independent product specification is tracked.

## Repository structure

| Path | Responsibility |
|---|---|
| `backend/app/main.py` | FastAPI application and route registration. |
| `backend/app/api/` | Health, repository, and streaming ask endpoints; current-user dependency. |
| `backend/app/core/` | Settings, database session, logging, and Fernet token encryption helpers. |
| `backend/app/models/` | SQLAlchemy `User` and `Repo` models and shared base. |
| `backend/app/schemas/` | Pydantic request/response models. |
| `backend/app/rag/` | GitHub API access, clone/fetch, source filtering/chunking, embeddings, Qdrant and BM25 indexing, and hybrid retrieval. |
| `backend/app/mcp_servers/` | Standalone GitHub and repository-search MCP servers. |
| `backend/app/mcp_client/` | MCP server connection and tool-loading cache. |
| `backend/alembic/` | Database migration environment and initial schema migration. |
| `backend/tests/` | Tests for ask streaming, chunking, MCP behavior, and retrieval ranking. |
| `backend/requirements.txt` | Python application and test dependencies. |
| `backend/Dockerfile`, `docker-compose.yml` | Container image and local service topology. |
| `.env.example` | Environment variable template. |

There is currently no tracked frontend, OAuth route, agent workflow, or API route for invoking the MCP tools.

## Completed phases

### Phase 1 — Backend foundation

**Evidence:** Initial project commit `219925b` (2026-10-11).

- Created the FastAPI application and health endpoint.
- Added settings, async SQLAlchemy database setup, structured logging, and Fernet token encryption/decryption helpers.
- Defined `User` and `Repo` persistence models, including a unique per-user repository constraint and a cascading user/repository relationship.
- Added the initial Alembic migration for those tables.
- Added Docker Compose services for the API, PostgreSQL, Redis, and Qdrant, plus a Python 3.11 backend image.

**Boundary:** Authentication flows and user provisioning are not present in this phase's implementation; persisted users are expected by later endpoints.

### Phase 2 — Repository ingestion and hybrid RAG

**Evidence:** Commit `e90811e` (2026-10-20).

- Added repository connect/list/status endpoints. Connecting validates repository metadata through GitHub and schedules indexing with FastAPI background tasks.
- Implemented shallow GitHub clone/fetch, file exclusions and size limits, source-language detection, and chunking (Python AST-aware; line-window fallback for other supported file types).
- Added FastEmbed embeddings, Qdrant vector storage, and a per-user/per-repository local BM25 index.
- Implemented reciprocal-rank fusion for hybrid search.
- Added `POST /ask`: checks that the requested repository belongs to the current user and is indexed, retrieves context, streams Groq response tokens over SSE, and returns source citations.
- Added tests for chunking, retrieval fusion, and ask-stream events.

**Boundary:** The current user dependency is a development shim using `X-Dev-User` as a GitHub numeric ID. Repository indexing is an in-process background task; Redis is configured as a service but no task queue integration is present.

### Phase 3 — MCP tools and host client

**Evidence:** Commit `da3cc7d` (2026-10-26), branch `feature/mcp-servers`.

- Added a GitHub MCP server with `get_diff` and `post_review_comment` tools.
- Added a repository-search MCP server with user-scoped `search_code`.
- Added an MCP client that attempts to load each server independently, caches the resulting tools/connection status, and tolerates a server being unavailable.
- Added tests for structured GitHub errors, empty comment rejection, repository-not-ready handling, and MCP startup with servers unavailable.

**Boundary:** Tool servers and the host-side loader exist, but no current API route or agent workflow calls `load_tools()` or uses the loaded tools to perform an end-to-end review.

## Current status

**Development stage:** Phase 3 implementation is the latest committed phase; Phase 4 has not yet been implemented. The repository is a backend foundation with ingestion, hybrid retrieval, streaming RAG Q&A, and standalone MCP tools. The next integration step is to orchestrate those tools into a user-authorized agent workflow.

Current surfaces and gaps:

- Registered HTTP routes are `/health`, `/repos`, `/repos/{repo_id}/status`, and `/ask`.
- Repository access checks use the database user ID. In the current development shim, the client supplies that user's GitHub ID in `X-Dev-User`.
- GitHub OAuth settings exist, but no OAuth endpoints or callback flow are implemented.
- `load_tools()` is implemented but not referenced by the API or another workflow.
- The Groq model is used directly by `/ask`; the configured MCP tools are not currently available to it.
- The GitHub MCP server can post an external inline review comment, but no review orchestration, approval gate, or API integration is implemented.
- The tracked test suite covers selected units and endpoint behavior; it does not establish full end-to-end, OAuth, deployment, or live-provider behavior.
- `frontend/` is not present in tracked files. The `.gitignore` mentions `frontend/.env.local` as a future Phase 7 artifact.

## Remaining phases

The phase descriptions below distinguish repository-backed anchors from recommendations. The source code itself does not define a complete, approved plan for Phases 4 onward.

### Phase 4 — Agent orchestration and assisted code review (next)

**Basis:** Phase 3 provides standalone MCP tools and a cached loader; `langgraph`, `langchain`, and `langchain-mcp-adapters` are declared dependencies. No current API or agent invokes the tools. The following is the proposed implementation specification for the next phase, not a claim that the workflow already exists.

#### Objective

Deliver a backend workflow that reviews a pull request using its GitHub diff and, when available, relevant context from the user's indexed repository. Return review findings with defensible source locations. Make posting comments a separate, explicit, user-approved action. This phase builds on the existing development identity dependency; it must not make Phase 6 authentication harder to adopt.

#### Scope and boundaries

**In scope**

- An authenticated/current-user-scoped review request and review result contract.
- Orchestration connecting the current user, owned repository, GitHub diff, MCP repository search, and the configured Groq model.
- Structured findings, location validation, analysis-only results, and a separately authorized comment-post operation.
- Progress/error reporting and deterministic tests using mocked providers.

**Not in scope**

- Implementing GitHub OAuth or replacing `X-Dev-User` (Phase 6).
- Building the frontend or its approval UI (Phase 7); Phase 4 must nevertheless expose an API that can support explicit approval.
- Replacing the existing indexing system, adding a durable queue, or broad production hardening (Phase 5).
- Automatically approving, merging, pushing commits, or posting comments as a side effect of merely requesting a review.

#### Proposed user flow

1. The caller requests a review for a connected repository and pull-request number. The workflow resolves the caller through `get_current_user`, verifies the repository belongs to that user, and obtains the credential associated with that user.
2. The workflow fetches the PR diff using `get_diff`. If repository context is used, it verifies the index is `ready` and searches through the existing user-scoped `search_code` tool.
3. The model analyzes the diff and supporting context and returns structured findings. The service validates each finding against changed files/lines in the diff and prepares a preview. This step performs no GitHub write.
4. The caller receives the preview. A distinct confirmation request submits the selected findings for posting. The server rechecks ownership and authorization, validates the selected findings again, then calls `post_review_comment` for each approved finding.
5. The workflow reports per-comment success/failure; partial failure must not be presented as complete success. The caller can inspect the resulting GitHub comment links where available.

#### API contract to implement

The exact paths may follow existing naming conventions, but the service must provide the following two distinct operations:

| Operation | Suggested route | Request data | Behavior |
|---|---|---|---|
| Analyze PR | `POST /repos/{repo_id}/pull-requests/{pr_number}/review` | Optional review instructions; no token, user ID, or arbitrary owner/repository identity supplied by the model. | Performs read-only analysis and returns/streams findings plus an opaque review identifier if confirmation is a separate call. |
| Post approved findings | `POST /repos/{repo_id}/pull-requests/{pr_number}/review/{review_id}/comments` | The selected finding IDs (or equivalent validated finding references). | Revalidates review ownership, age/state, repository, PR, and diff locations before posting only selected comments. |

This route shape is a recommendation, not an existing API. Keep route/schema details consistent with the final design and document deviations. Derive `user_id`, GitHub owner/repository, and provider credentials server-side. Never accept a caller-provided `user_id` as proof of identity.

The analysis result should have a stable, typed shape containing at least:

- Review identifier and repository/PR identity.
- Findings, each with a stable finding ID, file path, changed line on the new side of the diff, concise title, evidence-based explanation, and severity/category if the model can provide one.
- Warnings such as unavailable repository index/context, without disguising tool failure as a clean review.
- Analysis status and whether comments can be posted.

The posting result should include per-finding outcome and GitHub URL/identifier on success. Never echo access tokens or include them in a model prompt, response, log, or persisted review artifact.

#### Implementation sequence and dependencies

1. **Define schemas and workflow states.** Add request/response schemas and enumerate states such as `validating`, `fetching_diff`, `retrieving_context`, `analyzing`, `awaiting_approval`, `posting`, `completed`, and `failed`. Specify which errors are terminal and whether a review is retained for later approval. If approval is a separate request, persist its state and bind it to the current user, repo, PR, and diff revision; do not rely on process-local state for a review that must survive a request boundary.
2. **Establish the authorization boundary.** Reuse `get_current_user`; query `Repo` by both `repo_id` and `user.id`. Decrypt only the matched user's stored token using `decrypt_token`. Confirm the repository's canonical `full_name` maps to the requested PR. Do not expose token-bearing tool inputs to the model.
3. **Make MCP tool use safe and explicit.** Load tools through `app/mcp_client/client.py`; verify the required tool is available before use. Wrap/bind tools in application code so trusted values (token, user ID, repo ID, owner/name) come from server-side context rather than model-generated arguments. The model must not be able to select another user's repository or arbitrary credentials. Treat missing-server/tool conditions as explicit workflow errors or documented degraded mode.
4. **Fetch and interpret the diff.** Call `get_diff` with the connected user's credential. Check its structured `ok`/`error` result, enforce an input-size limit, and parse changed files and new-side line ranges. Reject or clearly report empty, malformed, or oversized diffs. Do not treat a truncated diff as complete; if a bounded input strategy is needed, report what was omitted.
5. **Retrieve optional repository context.** Query only the verified `repo_id` and current user. If the index is not ready, either continue with diff-only analysis and explicitly mark the missing context, or fail according to the agreed contract; never claim repository context was used when it was not. Keep retrieved snippets bounded and label them as untrusted source data.
6. **Generate structured findings.** Use the configured model and a constrained output schema/parser. Instruct the model to report only actionable issues evidenced in the diff/context, and to return no finding when evidence is insufficient. Model output is untrusted: validate required fields, lengths, file paths, line numbers, and finding count before returning it.
7. **Validate comment locations.** Each postable finding must target a changed file and a valid new-side line accepted by GitHub inline review comments. Exclude invalid locations from posting and explain them in the preview; do not silently remap a line. Keep whole-review findings that cannot be anchored available as non-inline findings only if the response contract supports them.
8. **Separate analysis from side effects.** Analysis must never invoke `post_review_comment`. Require a distinct confirmation request for writes, bind it to an unexpired review owned by the same user and the same repo/PR/diff, allow only selected finding IDs, and prevent replay/duplicate posting. If persistent confirmation state is outside Phase 4 scope, choose and document a safe synchronous confirmation design rather than pretending a preview token is durable.
9. **Return progress and errors.** Prefer SSE to match `/ask` if the analysis is streamed. Define events for workflow stage, findings/preview, completion, and error; ensure errors are explicit, do not return success-shaped fallbacks, and do not leak secrets/provider response bodies. For comment posting, return per-comment outcomes and distinguish full, partial, and total failure.
10. **Test and document the workflow.** Add unit and API tests around mocked tools/model, then run the backend suite. Update API documentation or this project guide with the selected routes, request/response shapes, approval semantics, configuration, and remaining limitations.

#### Acceptance criteria

- An unauthenticated/missing development identity is rejected by the existing dependency; a user cannot review another user's repository by changing IDs.
- The server derives owner/repository and credentials from the verified database records. Secrets never enter model-visible arguments, responses, or logs.
- The analysis path obtains and checks the PR diff. Repository search is scoped and only used for a ready index; any degraded diff-only analysis is identified as such.
- Findings have validated structure and are anchored only to changed files/lines before they are offered as inline comments.
- Analysis causes zero GitHub write calls. Posting requires a distinct approval action, rechecks the caller and review binding, and posts only the selected validated findings.
- Missing tools, provider failures, malformed model output, invalid locations, and partial comment failures are visible and accurately represented.
- Automated tests prove the above without live GitHub, Qdrant, or Groq credentials. Existing tests continue to pass.
- The API contract and operation are documented sufficiently for a future frontend to implement the review and confirmation flow.

#### Test plan

- **Authorization:** missing user; malformed user header; unknown user; repo not found; repo owned by another user; mismatched PR/repository.
- **MCP availability:** GitHub server/tool absent; repository-search server absent with ready/not-ready index; structured `not_found`, `forbidden`, and timeout tool results.
- **Diff/context:** empty, malformed, and oversized diff; changed-line parsing; missing index; search failure; snippets bounded and correctly attributed.
- **Model output:** valid findings; no findings; malformed schema; too many/long findings; path traversal or unknown file; unchanged/out-of-range line; unsupported inline location.
- **Approval and side effects:** analysis never calls comment tool; absent/expired/wrong-user/wrong-repo review cannot post; only selected finding IDs post; duplicate confirmation does not duplicate comments; each tool failure appears in per-comment result.
- **API behavior:** request validation, expected status/error events, SSE event ordering if streaming, no token leakage, and regression coverage for existing `/ask` behavior.

#### Deliverables

- Review request/result and comment-posting schemas.
- Review orchestration module and API route(s), integrated with the current-user and repository ownership checks.
- Safe server-bound MCP tool invocation and diff/location validation.
- Mocked unit/API tests for the acceptance criteria.
- Updated API/project documentation and an explicit list of deferred Phase 5–7 work.

**Exit gate:** Phase 4 is complete only when all acceptance criteria pass and a review can be analyzed without side effects, explicitly approved, and posted with per-comment outcomes under the correct user/repository boundary.

### Phase 5 — Reliability and operational hardening (recommended)

**Basis:** This phase is not named in tracked source. It is recommended because indexing currently runs in-process, Redis is configured but unused, external-service integration has limited test coverage, and the API has no documented production-readiness gate.

**Tasks**

- Decide whether indexing should remain a FastAPI background task or move to durable queue workers; if adopting a queue, integrate Redis rather than leaving it as an unused service.
- Define retry, duplicate-request, cancellation, and stale-index behavior; persist actionable job status and make failure state observable.
- Add lifecycle/cleanup behavior for per-repository clones, BM25 files, and Qdrant collections when repositories are disconnected or re-indexed.
- Add health/readiness checks for the database and search dependencies, plus bounded timeouts and useful error reporting for provider failures.
- Expand mocked integration tests across connect → index → search → ask/review flows and migration setup.
- Review operational configuration, logging/secret handling, and container startup dependencies; document how to run tests and diagnose failures.

**Expected outcomes:** Indexing and external-service failures are recoverable and observable; resource cleanup and operational checks have explicit behavior; CI validation covers the critical workflows.

### Phase 6 — Replace development identity with GitHub authentication

**Repository anchor:** `backend/app/api/deps.py` explicitly describes `X-Dev-User` as a Phase 2 shim to be replaced in Phase 6. GitHub OAuth settings and JWT-related settings/dependencies already exist, but no OAuth routes or token/session flow are implemented.

**Tasks**

- Implement GitHub OAuth sign-in/callback with state validation and an explicit session/token strategy.
- Resolve authenticated identity to the existing `User` model, create/update user records, and securely persist provider credentials using the existing encryption helpers.
- Replace `X-Dev-User` in `get_current_user` with validated authentication; reject unauthenticated requests consistently.
- Define token refresh/revocation/logout behavior and protect browser sessions against CSRF as required by the chosen strategy.
- Add tests for callback errors, invalid/missing credentials, session expiry, user mapping, and cross-user repository access.

**Expected outcomes:** All user-scoped API and MCP operations derive identity from verified credentials, not a caller-controlled development header.

### Phase 7 — Frontend

**Repository anchor:** `.gitignore` includes future frontend output paths and a `frontend/.env.local` entry labelled for Phase 7. No frontend source, manifest, or build configuration is tracked.

**Tasks**

- Select and document the frontend stack and API/SSE consumption approach before implementation.
- Build sign-in and connected-repository screens, repository indexing/status feedback, and a Q&A view that renders streamed tokens and citations.
- Add the Phase 4 review flow, including review findings and explicit confirmation before posting comments.
- Handle authentication expiry, provider/API errors, empty results, and indexing/review in-progress states.
- Keep secrets server-side; configure frontend origins and credentials deliberately rather than exposing provider tokens in browser code.
- Add frontend tests and a build/type-check step; verify API integration against the backend.

**Expected outcomes:** Users can authenticate and use the implemented repository Q&A and review capabilities through a tested interface.

## Development roadmap

1. **Prepare the local backend.** Create `.env` from `.env.example`; provide non-placeholder application secrets and credentials for the services/features being exercised. Set a reachable `QDRANT_URL` (for Compose networking, the Qdrant service hostname is `qdrant`). Start services with `docker compose up --build`.
2. **Verify the current baseline.** From `backend`, run `python -m pytest`. Check `/health`, repository connect/index status, and `/ask` with a seeded development user and configured GitHub/Groq/Qdrant services. Do not treat unit tests alone as proof that live services are configured.
3. **Implement Phase 4 first.** Specify the review API contract, build the orchestration around the existing MCP tools, enforce user/repository scoping and the comment approval boundary, and add mocked tests before live-provider checks.
4. **Complete Phase 5 hardening.** Choose and implement durable indexing/retry and cleanup semantics; improve health/error behavior; expand workflow-level test coverage and CI validation.
5. **Implement Phase 6 authentication.** Replace the development header only after OAuth/session behavior and migrations are tested; preserve access isolation throughout the transition.
6. **Build Phase 7 frontend.** Use the stabilized API and authentication contract; cover Q&A streaming, citations, repository status, and the approved review flow.
7. **Release readiness.** Run backend and frontend tests/builds, verify migrations from a clean database, exercise user isolation and failure paths, check container startup/readiness, and document required configuration and deployment operations. No separate Phase 8 is defined in the current repository.

## Local validation reference

```powershell
docker compose up --build

Set-Location backend
python -m pytest
```

The API container applies Alembic migrations before starting Uvicorn. The sample environment contains placeholders: configure real local values before expecting database, GitHub, Groq, or Qdrant-backed operations to work.
