# Testing

## Python (pytest)

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Expected: `160 passed, 2 xfailed`. The two xfailed tests are documented limitations
(`tests/test_known_failures.py`): a slow fall at 0.7× scale that is still missed, and a deliberate lie-down that is flagged as a fall. Every test uses a temporary database and temporary
clips, so the project's real `fall_guardian.db` is not modified.

| File | Covers |
|---|---|
| `tests/test_legacy_suite.py` | The nine original test cases, kept by name |
| `tests/test_database.py` | Initialization, validation, incident lifecycle, duplicates, alerts, DB errors |
| `tests/test_fall_detector.py` | Accelerometer prototype: normal, fall-like, missing, malformed, missing model |
| `tests/test_emergency.py` | DEMO simulation, INTEGRATION statuses, exceptions, timeouts, partial failure, duplicates |
| `tests/test_vision.py` | Vision rules on synthetic clips, warm-up, unreadable and missing files |
| `tests/test_evidence.py` | Post-event evidence branches and input validation |
| `tests/test_agent.py` | Approval gating, trace, duplicate suppression, store step |
| `tests/test_aws_handler.py` | Lambda validation, idempotency, conditional writes, storage errors |
| `tests/test_end_to_end.py` | Video → detection → evidence → agent → approval → store → workflow → trace |
| `tests/test_known_failures.py` | Strict expected failures for two synthetic misses |

What these tests do not show: real-world fall detection performance, delivery of any
notification, or that any AWS resource works. They use synthetic clips, fake providers,
and a local table stand-in.

## Node.js

```bash
cd alexa_mcp_server && npm ci && npm run check && npm test     # expect 17 pass
cd aws_backend/lambda && npm ci && npm run check && npm test   # expect 7 pass
```

`npm ci` must be run first; without it `npm test` fails with "Cannot find module".

## Evaluation and benchmark

```bash
python -m evaluation.evaluate --labels evaluation/labels_synthetic.csv --out evaluation/results_synthetic
python -m evaluation.benchmark --clip evaluation/clips_synthetic/synthetic_fall.mp4 --runs 5
```

## Mutation checks (recommended)

Reintroduce a known defect in a scratch copy and confirm a test fails. Examples used in this
project: remove the `/execute_tool` token check; always report "no recovery"; allow duplicate
Lambda writes; let a timeout dispatch. Each was caught.

## Not covered by automated tests

- Real SMS, 911, smart-lock, dashboard, Alexa+, DynamoDB, SNS, Bedrock calls
- Real AWS deployment (see `aws/DEPLOY.md` for manual verification steps)
- Real video footage and real false-alarm rates
- Load, failover, rate limiting, TLS termination
