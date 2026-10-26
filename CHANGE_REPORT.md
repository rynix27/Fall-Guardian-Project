# Change report (competition hardening pass)

Baseline at the start of this pass: 120 Python tests passed, 2 of 4 synthetic fall clips detected, Alexa server had no authentication, Lambda created a new incident id on every request.

## Changes by file

| File | Original problem | Change | Why | Tests | Result |
|---|---|---|---|---|---|
| `alexa_mcp_server/index.js` | `/execute_tool` and `/emergencies/:id` unauthenticated; tool input unvalidated; inputs logged; no body limit | Bearer-token middleware (fails closed); tool-name and object validation; 16 KB limit; safe 400/413 errors; tool input not logged; `app.listen` only when run directly | F1–F4 in SECURITY_REVIEW.md | `test/api.test.js` (10 HTTP tests) + mutation check | 17/17 pass; mutant fails 3 |
| `alexa_mcp_server/package.json`, lockfile | axios 1.7.9 and express 4.21.2 carried known advisories | Pinned axios 1.20.0, express 4.22.3 | F8, F9 | `npm test`, `npm audit --omit=dev` | 0 production vulnerabilities |
| `aws/fall_event_handler.py` | New UUID per request → retries duplicate incidents; errors echoed payload | Required idempotency key; uuid5 incident id; conditional PutItem; 200 on duplicate; no payload echo; body size limit | F5, F6 | `tests/test_aws_handler.py` (15 tests) + mutant check | Pass; duplicate-allowing mutant fails 2 |
| `aws/local_table.py` | Stand-in did not enforce writes | Enforces `attribute_not_exists` like DynamoDB | Make duplicate tests meaningful | Via handler tests | Pass |
| `agent/approval_agent.py` | No event validation; no evidence step; store payload lacked idempotency key | Event and severity validation before any request; evidence window step with deterministic labels and severity policy; idempotency key = run id; evidence label in results and trace | Brief requirements C/D/E/F, agentic workflow, duplicate prevention | `tests/test_agent.py`, `tests/test_evidence.py` | Pass; evidence mutant fails 2 |
| `vision/evidence.py` (new) | — | Serves a 5 s post-event window from one pipeline run | Additional analysis step | `tests/test_evidence.py` | Pass |
| `vision/synthetic_clips.py` | — | Added `slow_fall`, `fall_then_up`, `long_lie`, `fall_recover` scenarios (last one is not in evaluation labels) | Harder cases and an evidence test | Evaluation and tests | Used as documented |
| `vision/fall_vision.py` | `aspect_before` mislabeled; drop measured in frame height (fixed earlier); no warm-up | Warm-up period; upright aspect recorded correctly; drop normalised to body height (earlier change, disclosed) | Correctness | `tests/test_vision.py` | Pass |
| `tests/test_known_failures.py` (new) | Two missed synthetic falls undocumented in tests | Strict xfail with diagnosed reasons | Do not hide failures; do not tune to pass | Runs in suite | 2 xfailed |
| `tests/test_end_to_end.py` (new) | No test of the full path | Video → detect → evidence → agent → approval → store → workflow → trace; success, denial, timeout, store failure, non-fall, replay | Brief section 13 | 6 tests | Pass |
| `evaluation/benchmark.py` (new) | No measured performance | Measures FPS, ms/frame, memory, event latency, hardware | Brief G | Run on 320×240 and upscaled 1280×720 | 812.7 and 304.1 median FPS |
| `run_cv_demo.py` | Did not use evidence | Passes evidence; shows evidence label | Demonstrate agentic effect | Run | Works |
| `docs/architecture.dot` | Showed Lambda call; no evidence step | Added evidence node; Lambda marked idempotent, tested, not deployed | Accuracy of the diagram | Rendered and checked | Matches code |
| `requirements.txt` | numpy 2.2.6, OpenCV 5.0.0.93 | Unchanged; verified in a fresh venv | — | Fresh install run | 157 pass |

## Not changed (considered and deferred, with reasons)

- **Person detector (YOLO or similar):** not added. It needs a model file downloaded from outside the repository and a license check. It also requires a dataset to validate against, which does not exist. Deferred.
- **Pose estimation and multi-person tracking:** not implemented. The current pipeline tracks the largest blob only. This is documented as a limitation, not claimed.
- **Frontend:** none exists in the project. None was built; the trace file and console output are the only status views.
- **COOL award:** not pursued. Eligibility requires execution on AWS Graviton (Arm). This build runs on x86 and no Graviton instance was used. No COOL benchmark exists.
- **LLM agent:** not used. The decision policy is deterministic.
- **Lambda (JavaScript) SDK v3 migration:** deferred (F10). The competition path uses the Python handler.
- **Real caregiver authentication (F15):** not implemented. Needs an identity provider; deferred.
- **Rate limiting, CORS, encryption at rest (F11–F14):** deployment-level controls; documented, not implemented in code.

## Test counts

| Suite | Before | After |
|---|---|---|
| Python (pytest) | 120 passed | 157 passed, 2 xfailed (expected failures) |
| Alexa server (node --test) | 7 | 17 |
| Lambda JavaScript (node --test) | 7 | 7 |

Mutation checks run during this pass (each one reintroduced a defect in a scratch copy):
removing the token check (3 tests fail), always reporting no recovery (2 fail), allowing
duplicate writes (2 fail), and allowing timeouts to dispatch (1 fails). All were caught.

---

# Change pass 2: vision correction and evidence-based review

Baseline: `BASELINE_REPORT.md`. Metrics: `EVALUATION_REPORT.md`, `evaluation/metrics_summary.json`.

| File | Problem found | Change | Why | Tests | Outcome |
|---|---|---|---|---|---|
| `vision/fall_vision.py` | Hold condition cancelled by a small centroid rise while standing (`fall_then_up`) | Latched drop: largest drop in the lying episode is kept | Standing up should not erase an already-satisfied condition | `test_regression_fall_then_standing_is_detected`; mutant (no latch) fails | Dev: detected. Held-out: 4 → 7 detected overall (with grace) |
| `vision/fall_vision.py` | Lying episode reset by a box-shape jump while the body stays down (`slow_fall`): background absorption | Grace period (0.5 s) inside lying episodes, centroid must stay low (`lying_grace_s`, `grace_cy_tol`) | Segmentation drift should not reset the hold timer | `test_regression_slow_fall_is_detected`; mutant (no grace) fails | Dev: detected. Held-out: detected at 1.3×; still missed at 0.7× |
| `vision/fall_vision.py` | A video that opens but decodes no frames looked like "no falls" | Raises `IOError` when zero frames are decoded | A failure must not look like a normal result | `test_file_that_opens_but_decodes_no_frames_is_an_error`; guard mutant fails | Fixed |
| `vision/synthetic_clips.py` | No way to generate held-out variants; no intentional lie-down negative | `scale` parameter (default 1.0 unchanged); `intentional_lie` scenario | Held-out evaluation and the intentional-vs-slow-fall trade-off | Generation verified; evaluation run | 16 held-out clips generated |
| `tests/test_known_failures.py` | Two strict expected-failure tests guarded misses that the fix resolved; docstring diagnosis was wrong | Converted to regression tests asserting the desired behaviour; docstring corrected; added two new documented expected failures (slow fall at 0.7×, intentional lie-down false alarm) | Tests must reflect current behaviour without deletion or weakened assertions | 2 regression pass; 2 new xfail (strict) | Suite: 160 passed, 2 xfailed |
| `evaluation/` | Metrics not reproducible from archived results; no held-out set | Held-out labels, archived pre-change results, `metrics_summary.json`, `results_heldout.json` | Reproducibility; separate development and held-out evidence | Recomputed metrics agree with raw counts | Done |

## Two corrections to earlier statements

1. The earlier diagnosis of `slow_fall` as a transition-window problem was incorrect. The cause is background absorption resetting the hold timer (see `BASELINE_REPORT.md`).
2. The earlier diagnosis of `fall_then_up` as "lying shorter than hold" was incomplete. The hold was met; the drop condition was not satisfied on that frame.

## Result summary

| Set | Before | After |
|---|---|---|
| Development (7 clips, used for design) | Recall 0.50, specificity 1.00 | Recall 1.00, specificity 1.00 (in-sample) |
| Synthetic comparison set (16 clips; reviewed during debugging) | Recall 0.50, specificity 1.00 | Recall 0.875, specificity 0.875 (one false alarm: intentional lie-down) |

## Test counts

| Suite | Before this pass | After |
|---|---|---|
| Python (pytest) | 157 passed, 2 xfailed | 160 passed, 2 xfailed |
| Alexa server (Node) | 17 | 17 |
| Lambda (Node) | 7 | 7 |

## Mutation checks in this pass

Latch removed: one regression test fails. Grace removed: two regression tests fail. Zero-frame
guard removed: its test fails. All caught.

## Not done in this pass (with reasons)

- **Neural person detector (YOLO or similar):** not added. Needs a model download with licence and checksum verification, and a labelled set to validate against. No such set exists here.
- **Pose estimation and keypoints:** not implemented. Would need a model download, as above.
- **Multi-person tracking:** not implemented. The pipeline still uses the largest blob.
- **Full state machine with HUMAN_REVIEW_REQUIRED, TRACKING_LOST, PROCESSING_ERROR states:** not implemented as named states. Current states are NO_PERSON, WARMUP, UPRIGHT, OTHER_POSTURE, LYING_CANDIDATE, FALL_EVENT. Human review is handled by the agent, not as a vision state. This gap is stated in the checklist.
- **Shared event schema module across Python, JavaScript, database and AWS:** not consolidated in this pass. Validation exists in the agent and in the Lambda, and they are not yet generated from one schema.
- **Caregiver authorization:** unchanged (not authenticated).
- **Frontend:** none exists; none was built.
- **COOL award:** not pursued (no Graviton execution).


---

# Change pass 3: safety defaults, contracts, sources, and audit

Audit: `docs/ENGINEERING_AUDIT.md`. Verification: `docs/FINAL_VERIFICATION.md`.

| File | Problem | Change | Tests | Outcome |
|---|---|---|---|---|
| `run_cv_demo.py` | Demo auto-approved and ran the workflow with no decision | Default `--approval deny`; approve, timeout and ask are explicit; output labels the source as simulated; `--video` added | `tests/test_demo_safety.py` (3); mutation fails 1 | Unattended run takes no action |
| `agent/approval_ledger.py` (new) | No record of decisions; repeats and late answers not handled | One record per request; PENDING → APPROVED/DENIED/EXPIRED; duplicates never dispatch; conflicts and unknown ids rejected | `tests/test_approval_ledger.py` (13) | Verified |
| `agent/approval_agent.py` | A late approval could still dispatch; decisions not recorded with operator | Ledger gates dispatch; operator id in trace; store payload aligned with contract | `test_approval_arriving_after_expiry…`, `test_decision_trace_records_operator…` | Verified |
| `agent/approval_agent.py` | Evidence `UNRESOLVED_TRACKING_LOST` used for tracking loss and for too few frames | Added `INSUFFICIENT_EVIDENCE`; empty window is insufficient | `tests/test_evidence.py` (updated) | Verified |
| `contracts/incident_contract.py` (new) + `contracts/examples/` (23 fixtures) | No single contract; error handling ad hoc | Versioned contract (`1.0`), stable error codes, messages never echo values, size limit | `tests/test_contracts.py` (parametrised over fixtures) | Verified |
| `aws/fall_event_handler.py` | Accepted unknown fields and naive timestamps; keys up to 128 chars; silent default table | Matches contract: unknown fields rejected; timezone required; keys ≤ 64; table name validated; configuration error returns 500 | `tests/test_contracts.py` drift test; `tests/test_aws_handler.py` | Verified locally |
| `aws/local_table.py` | Stand-in did not model the conditional write precisely | Raises the same exception code DynamoDB uses | Existing handler tests | Verified locally |
| `vision/sources.py` (new) | No explicit source selection; no camera error path | `file:`, `synthetic:`, `camera:` specs; clear errors; camera path opens only when asked | `tests/test_sources.py` (11), including a fake closed camera | File and synthetic verified; camera not run on hardware |
| `docs/` | Required deliverables missing | `ENGINEERING_AUDIT.md`, `DEMO_SCRIPT.md`, `PROJECT_SUMMARY.md`, `FINAL_VERIFICATION.md` | Commands in `FINAL_VERIFICATION.md` | Written from verified results |

## Bugs found by the new tests and fixed

- Lambda accepted naive timestamps (drift from the contract).
- Agent sent an undeclared field that the stricter Lambda rejected (found by end-to-end tests).

## Not changed in this pass (and why)

- **Detector and thresholds:** unchanged, so the evaluation is not re-tuned.
- **Person detector, tracker, named state machine:** not implemented; each needs model weights, validation data, or a larger refactor than this pass allowed.
- **Legacy JavaScript Lambda migration to SDK v3:** not performed. The competition path does not use it; an untested migration is riskier than documenting it.
- **Durable approvals and caregiver authentication:** not implemented; they need storage and an identity provider.
- **Rate limiting:** not added. An in-process limiter would not protect multiple instances.

## Test counts

| Suite | Previous | Now |
|---|---|---|
| Python (pytest) | 160 passed, 2 xfailed | 237 passed, 2 xfailed |
| Alexa server (Node) | 17 | 17 |
| Lambda (Node) | 7 | 7 |


---

# Change pass 4: durable approvals

| File | Problem | Change | Tests | Outcome |
|---|---|---|---|---|
| `agent/approval_ledger.py` | Decisions lost on restart; not shared between processes | `DurableApprovalLedger` (SQLite): single conditional decision per request inside `BEGIN IMMEDIATE`; wall-clock expiry; same outcomes as the in-memory ledger | `tests/test_durable_ledger.py` (7): restart, conflicts after restart, expiry after restart, 30×12 concurrent decisions, unknown and invalid input, duplicate ids, unwritable path raises | Single host verified; multi-host not implemented |
| `tests/test_durable_ledger.py` | First race test silently dropped thread errors and could pass with a broken guard | Errors are collected and fail the test; each round checks all contenders reported back | Stress test | A weakened guard was caught in 1 of 5 runs. Stated as a limit. |
| `run_cv_demo.py` | No way to persist decisions from the demo | `--ledger-db PATH` | `tests/test_demo_safety.py` (new test) | Verified |

Limit: the race test is a regression check. The concurrency guarantee rests on `BEGIN IMMEDIATE`.
A deterministic interleaving test would need a hook inside `decide()`; that is future work.
