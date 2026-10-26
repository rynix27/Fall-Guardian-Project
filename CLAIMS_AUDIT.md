# Claims audit

This file records claims that appeared in earlier project documents, whether they were
supported, and what was changed. Earlier documents are not kept in this release.

## Removed as unsupported (no evidence in the project)

| Claim | Where it appeared | Action |
|---|---|---|
| "95% accuracy" / "95%+ accuracy on test data" | README, MEDICAL_VALIDATION, SPRINT_PLAN, AUDIT_REPORT_FINAL | Removed. No labelled dataset or evaluation exists. |
| "Healthcare provider validated", "Reviewed & approved by Dr. Sarah Chen, MD (Stanford)" | README, MEDICAL_VALIDATION, INDEX | Removed. No such review is documented or evidenced. Do not reinstate without a signed, dated document from the named person. |
| "Production-ready" / "PRODUCTION READY" | README, README_FINAL, INDEX, AUDIT_REPORT_FINAL | Removed. The software is a research prototype. |
| "Clinically validated" | Earlier README and reports | Removed. |
| "<300 ms detection time" | README, AUDIT_REPORT_FINAL | Removed. No timing benchmark exists for detection. |
| "Emergency services dispatched", "Smart lock unlocked", "Fire TV alert sent", "SMS sent" | Alexa server, Lambda, emergency service (INTEGRATION branch) | Replaced by per-channel statuses. Those actions did not occur. |
| "HIPAA-compliant logging" | CONFIG.md | Removed. No HIPAA compliance measures exist. |
| Dispatcher IDs, "Ambulance-1 / Fire-1" units, ETA "4 minutes" | Alexa server 911 handler, Bedrock mock | Removed. Invented values. |
| "Likely injury present" / "Paramedics ETA 4 minutes" | Bedrock fallback text | Replaced with an explicit UNVERIFIED label. |
| "Code coverage 95%+", "Response time ~4 ms" as quality metrics | Earlier DELIVERABLES_INDEX | Removed. Coverage was never measured. |
| "Fall detected with 80% confidence" | Demo output | Replaced by `prototype_score` (uncalibrated). |
| Budget ($1.62M), CPT codes, predicate-device K-numbers, insurance ROI | Earlier PRODUCTION_ROADMAP / HEALTHCARE_COMPLIANCE_GUIDE | Not based on evidence; not included in this release. |

## Code defects found and fixed during this audit

| Defect | Effect before fix | Fix |
|---|---|---|
| `python -m pytest` collected 0 tests (exit 5) | No automated tests ran under pytest | Tests moved to `tests/` with pytest-discoverable names |
| INTEGRATION mode returned SUCCESS for unimplemented actions | False success reports | Unconfigured channels → NOT_CONFIGURED |
| `log_fall` set `notified = 1` | Database recorded notification that never happened | Set to 0 |
| Alerts stored with status `sent` | Simulated/logged alerts looked delivered | Status records what happened (SIMULATED, NOT_CONFIGURED, FAILED, TIMEOUT, SENT) |
| `timeout_ms` accepted but unused | No timeout behavior | Each provider runs under a real timeout |
| Missing model file silently fell back to heuristic | Operator unaware | `model_status` = MISSING, `detection_method` reported |
| Tests and demo wrote to the real `fall_guardian.db` | Personal-looking records accumulated | Tests use temporary files; `FALL_GUARDIAN_DB` override |
| `validateEvent` threw TypeError on missing accelerometer | Lambda crashed instead of returning a validation error | Fixed; covered by tests |
| Bedrock module used `'test-key'` placeholder and fabricated medical mock text | Placeholder sent to API; invented clinical facts could reach dispatch script | No placeholder key; placeholder text makes no medical claim |
| Voice confirmation resolved with `prompt_sent: true` | Prompt claimed without being sent | Returns NOT_IMPLEMENTED |
| Lambda reported `NOTIFICATION_SENT` even when SNS was not configured or failed | False notification claim | Real notification status reported |
| `requirements.txt` pinned TensorFlow 2.14, which does not support Python 3.12 | Install failed on Python 3.12 | Core requirements split from optional ML requirements |
| `aws-backend/` directory name inconsistent with Python package naming | Confusing docs | Renamed to `aws_backend/` |
| No `package.json` for Node components | No reproducible Node install | Added manifests and lockfiles |


## Claims added in the competition build, and their status

| Claim | Status |
|---|---|
| The pipeline uses OpenCV 5 | True. `opencv-python-headless==5.0.0.93`; MOG2, contours and video I/O are called in `vision/fall_vision.py`. |
| The pipeline detects falls | Partly. Detects falls on synthetic clips with the rules in the report. Not measured on real footage. |
| Synthetic sensitivity 0.50, specificity 1.00 | True for those 7 clips only. Confidence intervals are wide. Not a performance estimate. |
| The agent only runs the workflow after approval | True and tested, including a mutation check. |
| The AWS component stores approved events | Code tested with a fake table. **Not deployed**; no AWS evidence exists yet. |
| The architecture diagram shows the Lambda being called | Corrected: the agent now calls the store step on approval. Before that, the diagram showed a connection the code did not have. |
| Emergency actions are simulated | True in this build. |


## Claims made in the hardening pass

| Claim | Status |
|---|---|
| The Alexa HTTP API requires a bearer token on sensitive endpoints | True. Tested over HTTP; mutation check confirms the tests fail without it. |
| Lambda retries do not create duplicate incidents | True for the Python handler with the conditional-write rule, tested against a local stand-in that enforces the same rule. **Not verified against real DynamoDB.** |
| Vision pipeline runs on OpenCV 5 | True. `cv2.__version__` is 5.0.0 in the test environment. |
| Agent severity and request change based on visual evidence | True and tested on synthetic clips. Deterministic rules, not a learned model. |
| Measured speed: 762 median FPS at 320×240 on a 1-core Xeon (earlier run: 813) | True for that machine and clip (`evaluation/benchmark_results.json`). Run-to-run variation about ±10%. Not a general claim. |
| Production npm dependencies have 0 known vulnerabilities | True at the time of the audit (`npm audit --omit=dev`). Re-check before submission. |
| The JavaScript Lambda is secure | **Not claimed.** It still uses aws-sdk v2 (end-of-life, 2 moderate advisories). |
| Detection accuracy | **Not claimed.** Held-out synthetic: 7 of 8 falls detected, 1 false alarm (16 clips). Development (in-sample): 4 of 4. Neither is a real-world measure. |
| Earlier diagnosis of the missed falls (transition window, short lying) | **Corrected.** Slow fall: background absorption reset the hold timer. Brief fall: centroid rise cancelled the drop condition on the frame the hold was met. |
| Fixes improve detection | **Partly supported.** Held-out recall rose from 0.50 to 0.875, with one new false alarm. Two fixes were applied together and not separated by ablation. |
