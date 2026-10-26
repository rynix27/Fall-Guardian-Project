# Security review

**Scope and method.** A focused manual review of the project plus automated checks
(regex secret scan, `npm audit`, the test suite, and mutation checks on the security
controls). This is **not** an exhaustive audit and has not been reviewed by a third party.

## 1. Threat model (short)

| Asset | Threat | Relevant control |
|---|---|---|
| Patient and contact data in SQLite and DynamoDB | Unauthorized read or write | Token auth on the HTTP API; least-privilege IAM intent; no data in logs |
| Emergency actions | Forged or replayed approvals or events | Approval gate in the agent; idempotency keys; event validation |
| Alexa MCP HTTP API | Unauthenticated tool execution or status lookup | Bearer token, fail closed, input validation, body size limit |
| Video | Privacy exposure | Video read locally; only event fields leave the machine |
| Dependencies | Known vulnerabilities | `npm audit` on Node packages; pinned versions |

## 2. Findings and status

| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | Alexa `/execute_tool` and `/emergencies/:id` had no authentication | High | **Fixed.** Bearer token, fails closed with 503 if no token configured. Tested over HTTP, including a mutation check. |
| F2 | Tool name and input were not validated before dispatch | Medium | **Fixed.** Unknown tool names and non-object inputs return 400. Tested. |
| F3 | No request size limit on the HTTP API | Medium | **Fixed.** 16 KB JSON limit; 413 on oversize; malformed JSON returns 400 with no stack trace. Tested. |
| F4 | Tool inputs (which can contain patient data) were logged | Medium | **Fixed.** Only the tool name is logged. |
| F5 | Lambda generated a new UUID per request, so retries created duplicate incidents | High | **Fixed.** Client idempotency key; incident id derived with uuid5; conditional write. Duplicate returns 200. Tested with a conditional-write stand-in. |
| F6 | Lambda error responses could echo personal data | Low | **Fixed.** Validation errors describe fields without echoing the payload. Tested. |
| F7 | Hard-coded API placeholder key (`test-key`) in the Bedrock module | Medium | Fixed in the earlier release: no key is used without configuration. |
| F8 | `axios` 1.7.9 had a high-severity SSRF/credential-leak advisory | High | **Fixed.** Bumped to 1.20.0. `npm audit --omit=dev` now reports 0 vulnerabilities. |
| F9 | `express` 4.21.2 pulled vulnerable `body-parser`, `qs`, `path-to-regexp` | High | **Fixed.** Bumped to 4.22.3. Covered by the same audit result. |
| F10 | Lambda (JavaScript, `aws-sdk` v2) depends on end-of-life SDK v2 | Medium | **Open.** `npm audit` reports 2 moderate issues; the only fix is a major migration to SDK v3. The competition path uses the Python handler; the JavaScript Lambda is legacy code. |
| F11 | No CORS or security headers on the HTTP API | Low | **Open.** Not added. The API is meant for server-to-server use; if a browser client is added, CORS must be set explicitly. |
| F12 | No rate limiting on the HTTP API | Medium | **Open.** Requires a reverse proxy or API gateway in deployment. |
| F13 | Token transport and storage are not encrypted in this build | Medium | **Open.** Deployment must use TLS (e.g., behind a load balancer or API Gateway). Local HTTP is for development only. |
| F14 | SQLite database is unencrypted on disk | Medium | **Open.** Protect with OS file permissions and full-disk encryption. Not implemented in code. |
| F15 | Caregiver approval is not authenticated | High | **Open.** The console approval and the simulated notifier have no identity check. A real deployment needs authenticated caregivers before approvals count. |

## 3. Secret scanning

A regex scan for AWS access-key IDs, private-key blocks, Anthropic and Slack token prefixes,
and hard-coded `password=`/`api_key=` assignments found **no matches** in the project.
The only token-like string is a fake value in `alexa_mcp_server/test/api.test.js`.
No real secret was found, so no rotation is required by this review.

## 4. Dependency audit

| Package set | Before | After |
|---|---|---|
| `alexa_mcp_server` (production) | 5 vulnerabilities (3 high, 2 moderate) | **0** |
| `aws_backend/lambda` | 2 moderate (aws-sdk v2, uuid) | 2 moderate (open, F10) |
| Python (`requirements.txt`) | Not audited with a vulnerability database in this build | Open. Run `pip-audit` before submission. |

## 5. Authentication and authorization

- **Authentication:** bearer token on `/execute_tool` and `/emergencies/:id`. Comparison is constant-time.
- **Authorization:** one shared token gives full access to both endpoints. There are no per-user roles. This is acceptable for a demo and not for multi-user production.
- **Approvals:** not authenticated (F15). The agent trusts the approval source it was given.

## 6. Data protection

- Video is processed locally. The code in this repository does not upload video.
- Lambda stores only: incident id, user id, event type, timestamp, decision, idempotency key, stored time, source label.
- No names, contact numbers, or video frames are sent to AWS by this code.
- Trace files contain event metadata and decisions, not frames or personal names. They are local files; protect them.
- Retention and deletion: not automated. Delete the DynamoDB table and local database when finished (see DEPLOYMENT_GUIDE.md).

## 7. Remaining risks (summary)

F10, F11, F12, F13, F14, F15. Items F13 and F15 are the most important before any real use.
None of this review should be read as evidence of compliance with any regulation.


## Pass 3 additions

| # | Item | Status |
|---|---|---|
| F16 | Demo auto-approved emergency workflow by default | **Fixed.** Default is deny; approval is an explicit, labelled simulation choice. |
| F17 | Late or repeated approvals could dispatch | **Fixed** for the in-process agent by the approval ledger. |
| F18 | Lambda accepted unknown fields, naive timestamps, and up to 128-character keys | **Fixed**; matches the shared contract. |
| F19 | Misconfigured table name silently fell back to a default | **Fixed**: returns a generic 500. |
| F20 | Approval ledger was in memory only | **Partly fixed.** SQLite-backed ledger keeps decisions across restarts and is safe for several processes on one host. **Still open** across hosts: needs a conditional write in shared storage. |
| F21 | Caregiver identity is a string from the approval source, not verified | **Open.** Needs an identity provider. |
| F22 | No rate limiting on the HTTP API | **Open.** Needs a gateway or shared limiter; an in-process limiter is not claimed. |
| F23 | Legacy JavaScript Lambda uses aws-sdk v2 (end-of-life) with 2 moderate advisories | **Open.** Not on the competition path. |
