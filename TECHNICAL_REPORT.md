# Fall Guardian: human-approved, evidence-aware vision fall alerts (technical report)

**Status: research prototype.** Not a medical device. Not clinically validated. Emergency
actions in this build are simulated. Numbers below come from runs in this repository and
name their source. **Not yet performed (as of submission preparation):** real-footage evaluation and live AWS deployment. The sections that describe them say so explicitly.

## 1. Abstract

Fall Guardian uses classic OpenCV 5 background subtraction and a posture state machine to
flag candidate falls in video. Before anything else happens, the system examines the five
seconds after the candidate, asks a caregiver to approve, and only then runs a (simulated)
emergency workflow and stores the approved event through an idempotent AWS Lambda handler.
On a 16-clip synthetic comparison set that was reviewed during debugging the detector caught 7 of 8 falls, with one
false alarm on a deliberate lie-down. These clips are not real footage, and that result is not
evidence of real-world performance.

## 2. Problem and motivation

Falls are a leading cause of injury for older adults, and time to help matters. Camera-based
alarms are prone to false positives (sitting down quickly, pets, objects), so the system
treats its output as a prompt for a human decision rather than as the decision itself.

Intended users: the monitored person; a caregiver who receives and decides on requests; and
developers who extend or test the system.

## 3. Proposed solution

Video → OpenCV 5 pipeline → candidate event → evidence window → agent → caregiver approval →
(on approval) store and workflow → trace. See `ARCHITECTURE.md` and `docs/architecture.png`.

## 4. Computer-vision method

- Frames are resized to 320 px width. The first 30 frames train the MOG2 background model and produce no output.
- The largest foreground contour above 600 px is taken as the person. Shape: height/width. Position: centroid normalised to frame height.
- State machine: upright (ratio ≥ 1.2) → lying (ratio ≤ 0.9) within 1.0 s of the last upright frame → lying episode. Within an episode, a brief jump in the box ratio does not end it if the centroid stays low (grace period 0.5 s). The largest centroid drop in the episode is latched. A candidate event is emitted when the latched drop is at least 0.25 standing body heights and the lying episode has lasted at least 1.5 s.
- Thresholds were chosen by reasoning about body geometry. The drop was first measured in frame height and later in body height; the grace period and latched drop were added after viewing development clips. Held-out clips were generated afterwards with different person sizes and seeds, and they were used to check the change.

### Limits of this method

- Background absorption: a motionless person can still drift into the background over long periods; the grace period reduces but does not remove this.
- A slow fall at 0.7× person scale is still missed on held-out clips.
- A deliberate, slow lie-down is indistinguishable from a slow fall by posture. At 1.3× scale it produced one false alarm on held-out clips.
- A fall followed by standing up produces a candidate event. The agent labels it as recovered and still asks a human to review. This is by design, not a claim that the system can tell a fall from an intentional lie-down.
- Single largest blob: not a person tracker. Multiple people, camera motion, and poor lighting are not handled.
- No person detector, pose estimator, or learned classifier is used. Pose estimation and multi-person tracking are not implemented.

## 5. OpenCV 5 implementation

- Version: OpenCV 5.0.0, installed with `opencv-python-headless==5.0.0.93`, verified by running the pipeline on 5.0.0.
- Functions: `createBackgroundSubtractorMOG2`, `morphologyEx`, `findContours`, `boundingRect`, `contourArea`, `resize`, `VideoCapture`, `VideoWriter`.
- The OpenCV 4-era HOG person detector is not present in OpenCV 5; it is not used.

## 6. Agentic workflow

The agent performs three real actions that depend on visual evidence:

1. **Additional analysis.** It examines a defined window (5 s) after each candidate event.
2. **Decision with labels.** The window is classified as `RECOVERED_WITHIN_WINDOW`, `NO_RECOVERY_OBSERVED`, or `UNRESOLVED_TRACKING_LOST`. Rules are deterministic.
3. **Changed request and workflow.** The approval request carries the label; the recorded severity rises by 2 when the person stays down. The workflow runs only after approval.

Nothing in this build uses a language model. The agent cannot run tools based on model output. A recovered person is still sent for human review; the agent does not reject the event on the basis of visual evidence alone.

Demonstrated by `python run_cv_demo.py`, which writes the evidence step to `demo_trace.jsonl`.

## 7. AWS integration

- Lambda handler (`aws/fall_event_handler.py`, Python 3.12 runtime): validates the approved event, derives the incident id from an idempotency key, performs a conditional write, returns 201 (new), 200 (duplicate), 400 (invalid), or 500 (storage failure).
- Idempotency is tested against a local stand-in that enforces the same conditional-write rule. It has **not** been tested against real DynamoDB. **Not performed as of submission preparation.** No live DynamoDB invocation or CloudWatch evidence exists yet. The stored-record behaviour is tested against a local stand-in only (`aws/DEPLOY.md` gives the steps to produce evidence).
- IAM intent: `dynamodb:PutItem` on the one table, plus the AWS-managed Lambda logging policy.
- The HTTP API (Node) uses bearer-token authentication, fails closed, and rejects invalid input before dispatch. See `SECURITY_REVIEW.md`.

## 8. Evaluation

Full details: `EVALUATION_REPORT.md`. All numbers are from synthetic clips.

| Set | Before the change | After the change |
|---|---|---|
| Development (7 clips, used to design the change) | recall 0.50, specificity 1.00 | recall 1.00, specificity 1.00 (in-sample) |
| Synthetic comparison set (16 clips; reviewed during debugging) | recall 0.50 (CI 0.22–0.79), specificity 1.00 (CI 0.68–1.00) | recall 0.875 (CI 0.53–0.98), specificity 0.875 (CI 0.53–0.98) |

The 16-clip synthetic comparison result describes this generated set only and is not independent validation. Precision after the change is 0.875. The set contains one false alarm (a deliberate lie-down at 1.3×).

**Real clips: not performed as of submission preparation.** No consented real footage has been recorded or labelled, so no real-world accuracy is reported. The synthetic results above must not be read as evidence about real footage.

## 9. Performance (measured on this machine)

Intel Xeon 2.10 GHz, 1 logical CPU, no GPU, OpenCV 5.0.0, Python 3.12.3.

| Input | Median FPS | ms/frame | Peak memory | Event latency |
|---|---|---|---|---|
| 320×240 synthetic | 762 | 1.31 | 60 MB | 1.53 s |
| 1280×720 (upscaled from 320×240) | 329 | 3.04 | 73 MB | 1.53 s |

Earlier runs on the same machine gave 813 and 304 FPS; run-to-run variation is about ±10%.
No neural-network inference is involved, so no inference time is reported. Real camera input,
other hardware, and GPU were not measured.

## 10. Security and privacy

- Video is read locally. The code in this repository does not upload video.
- Only approved-event fields (user id, timestamp, decision, idempotency key, stored time, source) are sent to AWS.
- Token-protected HTTP API; no real secrets found by the scan; production npm dependencies show 0 known vulnerabilities at the time of audit.
- Open risks: caregiver approval is not authenticated; SQLite is unencrypted; no rate limiting or TLS in code; the JavaScript Lambda still uses end-of-life aws-sdk v2. See `SECURITY_REVIEW.md`.
- Consent: any real footage must be recorded with written consent from everyone shown. Do not include bystanders.

## 11. Limitations

- No real-footage evaluation. Seven synthetic clips cannot support any performance claim.
- Single person, fixed camera, good lighting assumed.
- Emergency channels are simulated. No real SMS, 911, lock, or dashboard integration.
- AWS component tested locally only; not deployed in this build.
- No COOL (Graviton) work.
- Timeouts never dispatch help automatically. That policy must be agreed with users and clinicians before any real use.

## 12. Future work

Record and label real footage with consent; split development and held-out data before tuning;
add a pretrained person detector through OpenCV's DNN module with a documented download and
license check; add pose-based posture features; multi-person tracking; deploy and monitor the
AWS component; authenticate caregivers; clinical and privacy review before any real use.

## 13. Conclusion

The project now has a working OpenCV 5 pipeline, an evidence-aware approval agent, an
idempotent AWS handler tested locally, and an authenticated HTTP API. Its detection quality
is not yet established. The strongest honest claim today is that the pipeline runs end to
end on synthetic video, that it detects most falls on held-out synthetic clips (7 of 8) with one
false alarm, and that the surrounding controls behave as tested.

## 14. References

- OpenCV 5 documentation (background subtraction MOG2, contour analysis): https://opencv.org
- OpenCV AI Competition 2026 overview: https://opencv26.devpost.com/
- Amazon DynamoDB conditional writes (documentation): https://docs.aws.amazon.com/amazondynamodb/
