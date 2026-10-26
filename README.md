# Fall Guardian: human-approved vision fall alerts (research prototype)

Fall Guardian runs an OpenCV 5 pipeline over video to flag candidate falls. Before anything
else happens, it examines the seconds after the candidate and asks a caregiver to approve.
Only an approval runs the emergency workflow, which is simulated in this build, and stores
the approved event through an idempotent AWS Lambda handler.

> **Research prototype. Not a medical device. Not clinically validated. Do not rely on it
> to summon help.** Emergency actions are simulated. Detection quality is not established:
> on 16 held-out synthetic clips it caught 7 of 8 falls with 1 false alarm, and no real footage has been evaluated.

Start here: `TECHNICAL_REPORT.md` · `ARCHITECTURE.md` · `EVALUATION_REPORT.md` ·
`SECURITY_REVIEW.md` · `DEPLOYMENT_GUIDE.md` · `SUBMISSION_CHECKLIST.md` · `CHANGE_REPORT.md`

## Status

| Feature | Status |
|---|---|
| OpenCV 5 vision pipeline (MOG2, contours, posture state machine) | COMPLETED AND VERIFIED (runs on OpenCV 5.0.0; tested on synthetic clips) |
| Detection quality on real footage | NOT IMPLEMENTED (no real footage evaluated) |
| Post-event evidence window that changes the approval request and severity | COMPLETED AND VERIFIED (deterministic rules, tested) |
| Human approval gate (approve, deny, timeout, invalid input) | COMPLETED AND VERIFIED (tested, including a mutation check) |
| Duplicate suppression and idempotent store | COMPLETED AND VERIFIED for local code; not against real DynamoDB |
| AWS Lambda + DynamoDB | IMPLEMENTED BUT NOT FULLY VERIFIED (not deployed; see `aws/DEPLOY.md`) |
| Emergency workflow channels (SMS, 911, lock, dashboard) | SIMULATED. No real delivery exists. |
| Authenticated HTTP API (Alexa MCP server) | COMPLETED AND VERIFIED (bearer token, fails closed, 17 Node tests) |
| Person detector (neural network), pose estimation, multi-person tracking | NOT IMPLEMENTED |
| Frontend / web UI | NOT IMPLEMENTED (console output and trace file only) |
| Caregiver identity verification | NOT IMPLEMENTED |
| Best Use of COOL Award (Graviton) | NOT IMPLEMENTED (not pursued; no Graviton execution) |
| Language-model agent | NOT IMPLEMENTED (decision policy is deterministic, by design) |

## Quick start (verified commands)

Requires Python 3.12 and Node.js 18 or later.

```bash
python3 -m venv venv && . venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q                      # expect: 245 passed, 2 xfailed
python run_cv_demo.py                    # synthetic clip -> evidence -> simulated DENY (default: no action)
python run_cv_demo.py --approval approve # simulated approval -> simulated workflow (labelled)
python run_cv_demo.py --video my.mp4     # your own video file (needs permission to use it)
python run_cv_demo.py --ledger-db approvals.db   # decisions persist across runs (one host)
python -m evaluation.evaluate --labels evaluation/labels_synthetic.csv --out evaluation/results_synthetic
python -m evaluation.benchmark --clip evaluation/clips_synthetic/synthetic_fall.mp4 --runs 5

cd alexa_mcp_server && npm ci && npm run check && npm test     # expect: 17 pass
cd ../aws_backend/lambda && npm ci && npm test                  # expect: 7 pass
```

`run_cv_demo.py` defaults to DENY for safety. Use `--ask` to enter a decision interactively, or explicitly pass `--approval approve` / `--approval deny` for a labelled simulated path.
The demo writes `demo_trace.jsonl` and `fall_guardian.db` in the current folder. Delete them to reset.

## How it works

1. `vision/fall_vision.py` reads a video and emits a candidate when the posture rule fires.
2. `vision/evidence.py` and `agent/approval_agent.py` examine the 5 s after the candidate and label it (recovered, no recovery, unresolved). Severity rises by 2 if the person stays down.
3. The caregiver is asked. Only APPROVED continues. DENIED and no-response take no automatic action.
4. On approval, `aws/fall_event_handler.py` stores the event idempotently, and `emergency_response_service.py` runs the simulated workflow.
5. Every step is written to a trace file.

## Known limits (short list)

- Evaluation includes a 7-clip development set and a 16-clip synthetic comparison set. The latter was reviewed during debugging and should not be treated as an independent validation set. No real footage or real-world accuracy claim.
- Held-out: a slow fall at 0.7× person scale is still missed; a deliberate lie-down at 1.3× scale is flagged as a fall (see `EVALUATION_REPORT.md`).
- Single person, fixed camera, good lighting.
- Caregiver approval is not authenticated.
- Lambda not deployed in this build. The JavaScript Lambda is legacy and uses aws-sdk v2.

## Evaluating on real clips

1. Record consented clips and fill `evaluation/labels_real.csv` (`path,label,dataset`), with `dataset=real`, `label=1` for falls and `0` otherwise.
2. Run `python -m evaluation.evaluate --labels evaluation/labels_real.csv --out evaluation/results_real`.
3. Report every error. Do not report results from clips you did not label before running.

## Repository layout

```
vision/       OpenCV 5 pipeline, evidence window, synthetic clip generator
agent/        Approval agent with evidence step and trace
aws/          Lambda handler (idempotent), local table stand-in, DEPLOY.md
evaluation/   Evaluation harness, benchmark, synthetic labels and results, real-label template
docs/         Architecture diagram (.dot, .svg, .png)
tests/        pytest suite
alexa_mcp_server/, aws_backend/lambda/   Node.js components with their own tests
emergency_response_service.py, database_setup.py   Workflow and storage
bee_detection/   Accelerometer prototype (legacy, not used by the vision path)
```

## Privacy and safety

- Video is read locally. Only approved-event fields leave the machine.
- Do not record anyone without written consent. Do not include bystanders.
- A timeout never dispatches help automatically. That policy must be agreed with users and clinicians before any real use.


## Safety defaults (pass 3)

- The CLI demo's default decision is **deny**. Nothing runs unless you choose `--approval approve`, and the output labels that choice as simulated.
- Each approval request is recorded once (`agent/approval_ledger.py`). Duplicates never dispatch; late approvals after expiry are refused. `DurableApprovalLedger` keeps decisions in SQLite across restarts (one host only).
- Stored records follow `contracts/incident_contract.py` (version 1.0). Shared examples in `contracts/examples/` are checked against both the contract and the Lambda handler.
- Evidence labels: RECOVERED_WITHIN_WINDOW, NO_RECOVERY_OBSERVED, UNRESOLVED_TRACKING_LOST (no person visible), INSUFFICIENT_EVIDENCE (too few frames or no window).

More detail: `docs/ENGINEERING_AUDIT.md`, `docs/DEMO_SCRIPT.md`, `docs/PROJECT_SUMMARY.md`, `docs/FINAL_VERIFICATION.md`.
