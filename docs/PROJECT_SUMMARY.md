# Fall Guardian: project summary

**Status: experimental research prototype.** Not a medical device, not clinically validated,
not connected to any emergency service. It does not protect anyone.

## Problem

Older people who fall at home may not be able to call for help, and help can come late.
Camera-based fall alarms are attractive but produce false alarms: a person sitting down quickly,
a pet, or a dropped object can look like a fall. Automated alarms that act on one frame are
dangerous in both directions.

## Solution

Fall Guardian treats a camera result as a question for a person. It:

1. Detects possible falls in video with OpenCV 5 (background subtraction and posture rules).
2. Examines the five seconds after each possible fall.
3. Labels what the window shows, and whether the evidence is sufficient.
4. Asks a caregiver to approve or deny. Silence is not approval.
5. Stores only approved incidents, idempotently, with a validated record.
6. Records every step in a trace.

## Key technical points

- **Evidence changes the request.** A person who stays down raises the recorded severity. A person who recovers is still sent for review, not dismissed.
- **Safe defaults.** The demo's default decision is deny. Expired or duplicate decisions cannot dispatch. Simulated actions are labelled.
- **One contract.** Stored records are validated by a versioned contract with stable error codes; a test checks that the Lambda agrees with the contract on shared examples.
- **Honest status.** Every channel reports SIMULATED, NOT_CONFIGURED, FAILED, TIMEOUT or SUCCESS. Nothing reports a delivery that did not happen.

## Architecture

See `docs/architecture.png` and `ARCHITECTURE.md`. The AWS Lambda is tested locally and not deployed.

## Evaluation

| Set | Clips | Result | Notes |
|---|---|---|---|
| Development | 7 | TP 4, FP 0, TN 3, FN 0 | In-sample; used to design the fixes |
| Synthetic comparison | 16 | TP 7, FP 1, TN 7, FN 1 | Reviewed during debugging; not independent validation; synthetic; small |

Held-out recall 0.875 (95% CI 0.53–0.98); specificity 0.875 (CI 0.53–0.98). These numbers
describe synthetic clips only. They do not estimate real-world performance.

Performance on the test machine (1 CPU, no GPU): about 760 frames per second at 320×240.

## Security and privacy

- Video is read locally. Only approved-event fields are sent to AWS: user id, timestamp, decision, idempotency key.
- The HTTP API requires a bearer token and fails closed without one. Request sizes are limited.
- No secrets are in the repository; a scan found none.
- Open issues: caregiver identity is not verified; approval durability is single-host only; no rate limiting; the legacy JavaScript Lambda still uses aws-sdk v2.

## Current limitations

- Synthetic evaluation only. No real footage.
- A single largest blob is tracked; there is no person detector and no multi-person tracking.
- Slow falls at small scale are missed; a deliberate lie-down can look like a fall.
- AWS is not deployed; the storage path is tested locally.
- The caregiver approval is simulated in every run in this repository.

## Future roadmap

1. Consented real footage, with a development/held-out split and false-alarm rates per hour.
2. A person detector with checked licence and weights, and a tracker.
3. Multi-host durable approval decisions (single-host SQLite durability is done) and authenticated caregivers.
4. Deployment with infrastructure-as-code and recorded evidence.
5. A clinical and privacy review before any real use.
