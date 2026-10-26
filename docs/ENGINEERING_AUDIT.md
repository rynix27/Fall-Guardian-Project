# Engineering audit

Scope: the repository as delivered in V2, then the changes in this pass. Commands and
results are in `docs/FINAL_VERIFICATION.md`.

## 1. Current architecture

| Layer | Component | Status |
|---|---|---|
| Vision | `vision/fall_vision.py`: MOG2 background subtraction, largest contour, posture state machine with grace period and latched drop | Implemented; tested on synthetic clips |
| Vision | `vision/evidence.py`: 5 s post-event window from one pipeline run | Implemented |
| Input | `vision/sources.py`: explicit `file:`, `synthetic:`, `camera:` specs with clear errors | Implemented; camera path not exercised (no camera) |
| Decision | `agent/approval_agent.py`: validation, evidence labels, approval request, store, workflow | Implemented |
| Decision | `agent/approval_ledger.py`: one decision per request, expiry, conflicts, duplicates; in-memory and SQLite-backed (`DurableApprovalLedger`) | Implemented; durable form survives restarts on one host |
| Contract | `contracts/incident_contract.py` + `contracts/examples/*.json` | Implemented; used by the Lambda drift test |
| Storage | `aws/fall_event_handler.py`: idempotent conditional write to DynamoDB | Implemented; tested with a local stand-in; not deployed |
| Local storage | `database_setup.py`: SQLite incidents, alerts, medications | Implemented |
| Workflow | `emergency_response_service.py`: per-channel statuses, all channels simulated | Implemented; simulated only |
| API | `alexa_mcp_server/index.js`: bearer-token auth on sensitive routes, body limit, validation | Implemented; tested over HTTP |
| Legacy | `aws_backend/lambda/fall_detector_trigger.js` (aws-sdk v2) | Legacy; not on the competition path |
| Legacy | `bee_detection/`, `ring_integration/`, `run_demo.py` | Legacy accelerometer path; not used by the vision path |

## 2. Main execution flow

1. A source is chosen explicitly (`file:`, `synthetic:` or `camera:`).
2. `VisionFallDetector.process_video` yields per-frame readings and candidate events.
3. For each candidate, `VideoEvidence.window_after` supplies the 5 s post-event readings.
4. `assess_evidence` assigns one of four labels: RECOVERED_WITHIN_WINDOW, NO_RECOVERY_OBSERVED,
   UNRESOLVED_TRACKING_LOST, INSUFFICIENT_EVIDENCE. Severity rises by 2 only for NO_RECOVERY_OBSERVED.
5. The agent opens a ledger request and asks the approval source. TIMEOUT expires the request.
6. The ledger decides. Only a recorded APPROVED outcome allows dispatch.
7. On dispatch: the store step (idempotent, keyed by run id) and the simulated workflow.
8. Every step is written to a JSON-lines trace.

## 3. Working features (verified in this pass)

- Vision pipeline on OpenCV 5.0.0; detection on the 7-clip development set and the 16-clip held-out set (see EVALUATION_REPORT.md).
- Human approval, denial, timeout, duplicate and conflicting decisions, and late approval after expiry.
- Evidence labels, including the split between tracking loss and insufficient evidence.
- Idempotent Lambda handler with the contract's validation rules; drift test against the contract.
- Authenticated HTTP API for the Alexa MCP server, with fail-closed behaviour and body limits.
- Demo in deny, approve, timeout, and interactive modes, plus `--video` for a file.

## 4. Bugs discovered and fixed in this pass

| # | Bug | Severity | Fix | Evidence |
|---|---|---|---|---|
| B1 | Demo auto-approved and ran the simulated workflow with no decision | High (unsafe default) | Default is `deny`; approval is an explicit flag and is labelled as simulated | `tests/test_demo_safety.py`; mutation (default=approve) fails 1 test |
| B2 | A source that answers after the deadline could still dispatch | High | Ledger refuses approval after expiry; `NO_ACTION` with `ledger_outcome=EXPIRED` | `test_approval_arriving_after_expiry_is_not_dispatched` |
| B3 | Repeated approvals had no record, so repeats were not detected | Medium | Per-request ledger; repeats return `ALREADY_DECIDED` with no dispatch | `tests/test_approval_ledger.py` |
| B4 | Lambda accepted unknown fields and timestamps without a timezone; the contract rejected both | Medium (storage ambiguity) | Lambda now rejects both, with the same rules as the contract | Drift test found it: `invalid__approved_naive_timestamp` |
| B5 | Lambda idempotency keys could be 128 characters; contract allows 64 | Low | Aligned to 64 | `invalid__approved_long_key` |
| B6 | A malformed `FALLS_TABLE` silently used a default | Medium | Configuration error returns 500 with a generic message | `tests/test_aws_handler.py` |
| B7 | Agent's store payload carried an undeclared `run_id` field; the stricter Lambda rejected every store | High once B4 was fixed | Payload aligned to the contract; run id travels as `idempotency_key` | Failing end-to-end tests exposed it |
| B8 | Evidence label `UNRESOLVED_TRACKING_LOST` covered both tracking loss and too-few frames | Medium (misleading audit trail) | Split into UNRESOLVED_TRACKING_LOST and INSUFFICIENT_EVIDENCE; an empty window is insufficient, not a loss | `tests/test_evidence.py` |
| B9 | Zero-frame video looked like "no falls" | Medium | Raises an error (fixed in the previous pass) | `test_file_that_opens_but_decodes_no_frames_is_an_error` |

## 5. Reliability problems

- **Ledger is single-host.** `DurableApprovalLedger` survives restarts and is safe for several processes on one machine that share the SQLite file. It is not a multi-host control: two machines cannot share a local SQLite file safely. A multi-host ledger needs a conditional write in shared storage (e.g. DynamoDB). Not implemented.
- **Timeout threads.** A console approval that times out leaves a daemon thread waiting for input. The ledger expires the request, so no action follows, but the thread is not reclaimed.
- **Camera path.** `open_camera` is written to fail clearly when no camera exists. It has not been run against real hardware.
- **Frame timing.** Thresholds are expressed in seconds, but the detector counts frames at the assumed FPS. Dropped frames and irregular timestamps are not modelled.

## 6. Security problems

- Caregiver approval has no authentication. Operator identity is a string supplied by the approval source (`simulated-operator`, `console-operator`). The ledger records it, but nothing verifies it.
- Bearer token is one shared secret with full access to both protected routes. No per-role authorization.
- No rate limiting. A rate limiter inside one process would not protect a multi-instance deployment, and none has been added.
- No CORS configuration. The API is intended for server-to-server use only.
- Legacy JavaScript Lambda uses aws-sdk v2 (end-of-life) and reports two moderate npm advisories.

## 7. Evaluation limitations

- 7 development clips and 16 held-out clips, all synthetic (a rectangle stands in for a person).
- Development results are in-sample; the 16-clip comparison set was reviewed during debugging and is not an independent validation set.
- The two fixes (grace period, latched drop) were applied together and not separated by ablation.
- No real footage; no false-alarm rate per hour; no per-scenario coverage beyond the scenario list.

## 8. AWS verification gaps

- Handler tested against a local conditional-write stand-in, not DynamoDB.
- No deployment, no CloudWatch logs, no IAM policy simulation against real roles.
- `aws/DEPLOY.md` gives the commands; they have not been executed against an account.
- No infrastructure-as-code template (SAM/CloudFormation) exists; the deployment is manual CLI steps.

## 9. Prioritised remaining fixes

1. Real footage evaluation with consent and a held-out split (requires people and recordings).
2. Multi-host durable approval decisions (a conditional write in DynamoDB), so decisions span machines. Single-host durability is implemented.
3. Authenticated caregiver identity for approvals (requires an identity provider).
4. Retire or migrate the legacy JavaScript Lambda; remove the aws-sdk v2 dependency.
5. Person detector and tracker (requires model weights with checked licence and checksum).
6. Event schema emitted by the detector itself (the contract currently validates at boundaries; the in-process agent still uses its own check).
7. Infrastructure-as-code template for the Lambda, table and role.

## 10. External work that cannot be completed locally

- AWS account, credentials, and deployment; live DynamoDB and CloudWatch verification.
- Consented real video and labelling.
- A camera and a physical test environment.
- A real notification or dispatch provider, and the legal and operational setup it needs. This project does not contact emergency services or caregivers.
- Competition registration, team information, the public repository, and the recorded demo.
