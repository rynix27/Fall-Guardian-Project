# Final verification report

Verified from the working copy after the final changes. Environment: Ubuntu 24.04.4 LTS,
Linux 6.18; Python 3.12.3; OpenCV 5.0.0 (`opencv-python-headless` 5.0.0.93, the only OpenCV
distribution installed); NumPy 2.2.6; Node.js v22.22.2; CPU: Intel Xeon 2.10 GHz, 1 logical CPU, no GPU.

## 1. Commands and results

| # | Command (from the project root) | Result |
|---|---|---|
| 1 | `python -m pytest -q` | exit 0; **245 passed, 2 xfailed** |
| 2 | `python -m pytest -q -rx` (xfail reasons) | `known_miss_slow_fall_small_person` (0.7× scale) and `known_false_alarm_intentional_lie_down` |
| 3 | `python -m compileall -q .` | exit 0 |
| 4 | `python -m evaluation.evaluate --labels evaluation/labels_synthetic.csv --out evaluation/results_synthetic` | exit 0; clips 7: TP 4, FP 0, TN 3, FN 0 |
| 5 | `python -m evaluation.evaluate --labels evaluation/labels_heldout.csv --out evaluation/results_heldout` | exit 0; clips 16: TP 7, FP 1, TN 7, FN 1 |
| 6 | `python run_cv_demo.py --approval deny` | exit 0; NO_ACTION; no WORKFLOW_RESULT |
| 7 | `python run_cv_demo.py --approval approve` | exit 0; WORKFLOW_RESULT with SIMULATED_ONLY; STORE_RESULT |
| 8 | `python run_cv_demo.py --approval timeout` | exit 0; NO_RESPONSE; no WORKFLOW_RESULT |
| 9 | `python run_cv_demo.py --video <real file> --approval deny` | exit 0 on a generated test clip; missing file gives exit 2 with a clear message |
| 10 | `python run_demo.py` (legacy accelerometer demo) | exit 0 |
| 11 | `cd alexa_mcp_server && npm ci && npm run check && npm test` | ci exit 0; check exit 0; **17 pass, 0 fail** |
| 12 | `cd alexa_mcp_server && npm audit --omit=dev` | **found 0 vulnerabilities** |
| 13 | `cd aws_backend/lambda && npm ci && npm run check && npm test` | ci exit 0; check exit 0; **7 pass, 0 fail** |
| 14 | `cd aws_backend/lambda && npm audit` | 2 moderate advisories, all from aws-sdk v2 (not fixed; see section 4) |

Not run in this pass: the benchmark (`evaluation/benchmark.py`). Its numbers in
`EVALUATION_REPORT.md` are from the previous pass and were not re-measured.

## 2. Detector results (unchanged in this pass)

The detector code was not modified in this pass, so the evaluation numbers are the same as in
the previous pass. Re-running reproduced them exactly (commands 4 and 5).

| Set | Recall | Specificity | Precision | F1 |
|---|---|---|---|---|
| Development (7, in-sample) | 1.000 | 1.000 | 1.000 | 1.000 |
| Held-out (16) | 0.875 | 0.875 | 0.875 | 0.875 |

Held-out 95% Wilson intervals: recall 0.53–0.98, specificity 0.53–0.98.

## 3. Specific checks requested

| Check | How it was verified | Result |
|---|---|---|
| Approval and rejection behaviour | `tests/test_agent.py`, `tests/test_approval_ledger.py`, `tests/test_demo_safety.py` | Pass |
| Concurrent approval decisions (durable ledger) | `tests/test_durable_ledger.py`: 30 rounds × 12 threads, exactly one recorded outcome per request, no thread errors | Pass. **Limit:** a deliberately weakened version was caught in only 1 of 5 runs. The guarantee rests on `BEGIN IMMEDIATE`; this stress test is a regression check, not a proof. |
| Restart survival of approvals | `tests/test_durable_ledger.py`: decision and expiry survive a new ledger instance | Pass (one host, one SQLite file) |
| Duplicate incident submission | `tests/test_aws_handler.py` (retry returns 200), `tests/test_end_to_end.py` (replay) | Pass against a local stand-in |
| Invalid event payloads | `tests/test_contracts.py` (23 fixtures with expected error codes) | Pass |
| Development demo cannot trigger real notifications | Demo uses only simulated channels; `tests/test_demo_safety.py`; channels are SIMULATED in DEMO mode | Pass (by construction and test) |
| Credentials not committed | Regex scan for AWS key IDs, private key blocks, Anthropic and Slack token prefixes | No matches (run before V2; re-run recommended before release) |
| Simulated AWS not described as live | Documents reviewed: `ARCHITECTURE.md`, `PROJECT_SUMMARY.md`, `README.md` | Consistent; AWS marked not deployed |
| Mutation checks | Unsafe demo default (1 test fails); removed token check (3 fail, previous pass); removed latch / grace (previous pass) | Caught |

## 4. Skipped, blocked, or failing

- **Skipped:** none in the Python suite.
- **Expected failures (2):** documented limitations; strict xfail, so they flag if they start passing.
- **Blocked:** live AWS deployment (no account); camera capture (no hardware); real footage (no consent-based recordings).
- **Failing:** none.
- **Advisories:** `aws_backend/lambda` reports 2 moderate advisories from `aws-sdk` v2 (end-of-life). The competition path uses the Python handler, so this is recorded as legacy debt, not fixed here.

## 5. Placeholders and partial features

- **Person detector.** Not implemented. The detector uses the largest moving blob, and that is not a person detector.
- **Tracking.** Single blob; no track identifiers across people.
- **Full named state machine** (HUMAN_REVIEW, TRACK_LOST, ERROR as states). Not implemented as named states; human review is handled by the agent.
- **Shared event schema emitted by the detector.** The contract validates at boundaries (Lambda, fixtures). The detector does not emit `schema_version`, and the agent still uses its own check.
- **Durable approvals.** The ledger is in memory.
- **Camera capture.** Code path exists with a clear error when no camera is present; not run on hardware.
- **Infrastructure as code.** None; manual CLI steps in `aws/DEPLOY.md`.
- **Frontend.** None. Not built.

## 6. Feature status

| Feature | Implementation status | Verification evidence | Remaining limitation |
|---|---|---|---|
| Vision pipeline on OpenCV 5 | VERIFIED | Runs on 5.0.0; commands 4–9 | Synthetic only |
| Detection quality | PARTIALLY VERIFIED | Held-out 7/8 recall, 1 false alarm | Synthetic; small; no real footage |
| Slow fall / fall-then-recovery | PARTIALLY VERIFIED | Regression tests pass; held-out 0.7× slow fall still missed | Scale-dependent |
| Tracking across frames | NOT IMPLEMENTED | — | Largest-blob only |
| Person detector | NOT IMPLEMENTED | — | Needs licensed weights and validation data |
| Evidence classification (4 labels) | VERIFIED | `tests/test_evidence.py` | Deterministic rules, not a model |
| Human approval, denial, timeout | VERIFIED | Agent, ledger, and demo tests | Operator identity not authenticated |
| Duplicate and conflicting decisions | VERIFIED | `tests/test_approval_ledger.py` | In memory; single process |
| Demo safe default (deny) | VERIFIED | `tests/test_demo_safety.py`; mutation check | — |
| Event contract with stable error codes | VERIFIED | 23 fixtures; error-code coverage test | Not yet emitted by the detector |
| Lambda idempotent storage | IMPLEMENTED BUT NOT VERIFIED against DynamoDB | Local stand-in tests | Not deployed |
| Lambda and contract agreement | VERIFIED | Drift test on approved fixtures | — |
| Table configuration validation | VERIFIED | `tests/test_aws_handler.py` | — |
| HTTP API authentication | VERIFIED | 17 Node tests over HTTP | Shared token; no roles |
| HTTP API input validation and body limit | VERIFIED | Node tests | No rate limiting |
| Emergency workflow channels | INTENTIONALLY OUT OF SCOPE for live use | Simulated and labelled | No real dispatch by design |
| Caregiver notification | INTENTIONALLY OUT OF SCOPE for live use | Console stand-in only | — |
| Video file input | VERIFIED | Command 9 on a generated clip | Other codecs not tested |
| Camera input | IMPLEMENTED BUT NOT VERIFIED | Missing-camera error tested with a fake capture | No hardware |
| Performance | VERIFIED (previous pass) | Benchmark in EVALUATION_REPORT.md | Not re-measured in this pass; one CPU |
| Legacy JavaScript Lambda (aws-sdk v2) | NOT IMPLEMENTED as a migrated component; legacy | npm audit: 2 moderate | Retire or migrate |
| Infrastructure as code | NOT IMPLEMENTED | — | Manual CLI steps only |
| Frontend | NOT IMPLEMENTED | — | Intentionally not built |
| Real footage validation | BLOCKED BY EXTERNAL REQUIREMENT | — | Needs consented recordings |
| Live AWS deployment | BLOCKED BY EXTERNAL REQUIREMENT | — | Needs an account and credentials |
| Competition registration | BLOCKED BY EXTERNAL REQUIREMENT | — | Needs the team's Devpost entry |

## 7. Quality assessment

Not rated against the 9/10 target. The main blockers to a higher rating are the ones listed in
`docs/ENGINEERING_AUDIT.md` section 9: no real-footage evaluation, no person detector or tracker,
no durable or authenticated approvals, and no live AWS deployment. Those cannot be closed in this
environment.
