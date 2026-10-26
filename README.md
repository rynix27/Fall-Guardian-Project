# Fall Guardian

### OpenCV-Based Fall Detection and Human-Approved Response Prototype

Fall Guardian is an experimental computer-vision project that analyzes
video for movement patterns that may indicate a fall, then routes
candidate events through a transparent, human-approval workflow.

The project combines an OpenCV 5 vision pipeline, deterministic
post-event evidence assessment, approval gating, event tracing, local
storage, and simulated emergency-response channels. It is designed as a
research and hackathon prototype---not as a medical device or a
production emergency-response service.

> \[!WARNING\] **Safety notice:** Fall Guardian is not clinically
> validated and must not be relied upon to summon help. Evaluation to
> date uses synthetic video only. Emergency-response channels are
> simulated, and the AWS integration has not been verified against a
> deployed AWS environment.

## Table of contents

-   [Project goals](#project-goals)
-   [Capabilities and implementation
    status](#capabilities-and-implementation-status)
-   [How it works](#how-it-works)
-   [Architecture](#architecture)
-   [Technology stack](#technology-stack)
-   [Repository structure](#repository-structure)
-   [Requirements](#requirements)
-   [Quick start](#quick-start)
-   [Run the demo](#run-the-demo)
-   [Testing](#testing)
-   [Evaluation](#evaluation)
-   [Security, privacy, and safety](#security-privacy-and-safety)
-   [Limitations](#limitations)
-   [Future work](#future-work)
-   [Contributing](#contributing)
-   [License](#license)

## Project goals

Falls can be difficult to distinguish from ordinary movements in video.
Fall Guardian explores whether a lightweight, interpretable
computer-vision pipeline can identify candidate fall events and provide
evidence to a human reviewer before any response workflow is initiated.

The project's goals are to:

-   Demonstrate video-based candidate fall detection using OpenCV.
-   Assess a short post-event video window for evidence of recovery or
    unresolved tracking.
-   Require an explicit human decision before the simulated response
    workflow proceeds.
-   Record workflow decisions and outcomes in a trace for review.
-   Evaluate the prototype with reproducible tests and clearly
    documented failure cases.

## Capabilities and implementation status

  -----------------------------------------------------------------------
  Component               Status                  Notes
  ----------------------- ----------------------- -----------------------
  OpenCV vision pipeline  Implemented and tested  Uses foreground motion,
                          on synthetic clips      contours, bounding-box
                                                  characteristics,
                                                  centroid movement, and
                                                  rule-based posture
                                                  logic.

  Post-event evidence     Implemented             Examines a 5-second
  assessment                                      window and labels the
                                                  evidence.

  Human approval gate     Implemented and tested  Supports approval,
                                                  denial, invalid input,
                                                  and no-response paths.

  Event trace             Implemented             Writes workflow steps
                                                  to JSON Lines.

  Local SQLite storage    Implemented             Used for local
                                                  incident/workflow data.

  Local idempotency       Implemented and tested  Supports local testing
  stand-in                                        of duplicate-write
                                                  behavior.

  AWS Lambda handler      Code present; cloud     Tests use local/fake
                          deployment unverified   components; real
                                                  DynamoDB integration
                                                  has not been verified.

  Emergency notifications Simulated               No real SMS,
  and response channels                           emergency-service, or
                                                  other external delivery
                                                  is performed.

  Authenticated           Code and tests present  Verify the server setup
  HTTP/MCP-style server                           and configuration
                                                  before exposing it to
                                                  any network.

  -----------------------------------------------------------------------

## How it works

1.  **Video input:** The vision pipeline reads a video file and
    processes its frames.
2.  **Candidate event detection:** OpenCV foreground/motion analysis and
    geometric features feed a deterministic posture/state rule. A match
    produces a *candidate* event, not a confirmed fall.
3.  **Post-event evidence:** The system examines the following 5 seconds
    of video and labels the observed evidence as one of:
    -   `RECOVERED_WITHIN_WINDOW`
    -   `NO_RECOVERY_OBSERVED`
    -   `UNRESOLVED_TRACKING_LOST`
4.  **Human approval:** The approval workflow presents the candidate and
    evidence label for a decision.
5.  **Gated event handling:** Only an explicit `APPROVED` decision
    proceeds to event storage and the simulated workflow. A denial or no
    response does not automatically dispatch help.
6.  **Trace:** Workflow steps are recorded in `demo_trace.jsonl` for
    inspection.

The decision policy is deterministic and rule-based. The project does
not use a language model to interpret video or generate tool calls.

## Architecture

``` mermaid
flowchart TD
    A[Video file] --> B[OpenCV 5 vision pipeline]
    B --> C[Candidate fall event]
    C --> D[5-second post-event evidence assessment]
    D --> E[Human approval request]
    E -->|Denied or no response| F[Trace only; no automatic action]
    E -->|Approved| G[Idempotent event handling]
    G --> H[Local table stand-in / unverified AWS handler]
    G --> I[Simulated response workflow]
    C --> J[JSONL execution trace]
    D --> J
    E --> J
    G --> J
```

**Deployment note:** The diagram describes the prototype's workflow. It
does not imply that AWS resources are deployed or that real emergency
notifications are delivered.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) and the files in `docs/` for
further implementation detail.

## Technology stack

-   **Python 3.12** --- primary application and evaluation code.
-   **OpenCV 5** --- video processing and computer vision.
-   **NumPy** --- numerical and array operations.
-   **pytest** --- Python automated tests.
-   **Node.js 18 or later** --- JavaScript server and Lambda-related
    components.
-   **SQLite** --- local persistence for incident/workflow records.
-   **AWS Lambda / DynamoDB code** --- integration code is included, but
    deployment and live cloud behavior are not verified.

The authoritative dependency lists are `requirements.txt` and the
`package.json` files in the JavaScript subprojects.

## Repository structure

``` text
fall-guardian/
├── agent/                  # Approval workflow and approval ledger
├── aws/                    # Event handler, local table stand-in, deployment notes
├── aws_backend/lambda/     # JavaScript Lambda component and tests
├── alexa_mcp_server/       # Token-protected prototype server and tests
├── bee_detection/          # Legacy accelerometer prototype; not used by vision path
├── contracts/              # Incident schema and examples
├── docs/                   # Project summary, engineering audit, diagrams, demo script
├── evaluation/             # Evaluation scripts, labels, results, and synthetic clips
├── tests/                  # Python automated tests
├── vision/                 # OpenCV pipeline, evidence logic, synthetic clip generator
├── database_setup.py       # Local SQLite setup
├── emergency_response_service.py
├── run_cv_demo.py          # Command-line demonstration
├── requirements.txt
├── ARCHITECTURE.md
├── EVALUATION_REPORT.md
├── SECURITY_REVIEW.md
├── TECHNICAL_REPORT.md
└── README.md
```

Some files and subprojects may have their own setup instructions. Review
the relevant documentation before running optional components.

## Requirements

-   Python 3.12 recommended.
-   Node.js 18 or later for the JavaScript subprojects.
-   Git, if cloning the repository.
-   A desktop environment is useful for inspecting local video files;
    the core demo is command-line based.

The Python dependencies are pinned in `requirements.txt`.

## Quick start

### 1. Clone the repository

``` bash
git clone https://github.com/rynix27/Fall-Guardian-Project.git
cd Fall-Guardian-Project
```

If the project files are inside a nested `fall-guardian/` directory in
the repository, enter that directory before continuing:

``` bash
cd fall-guardian
```

Run `dir` on Windows or `ls` on macOS/Linux to confirm that
`requirements.txt` and `run_cv_demo.py` are in the current directory.

### 2. Create a virtual environment

**Windows PowerShell**

``` powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux**

``` bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

``` bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Run the test suite

``` bash
python -m pytest -q
```

The repository's current test documentation contains differing expected
counts. Run the suite in your environment and report the actual result
from the current commit; do not rely on a stale count in documentation.

## Run the demo

Run the default demo:

``` bash
python run_cv_demo.py
```

The default path is designed to deny the request and take no response
action.

To request a decision interactively:

``` bash
python run_cv_demo.py --ask
```

To demonstrate a labelled simulated approval:

``` bash
python run_cv_demo.py --approval approve
```

To demonstrate a labelled simulated denial:

``` bash
python run_cv_demo.py --approval deny
```

To provide a video file:

``` bash
python run_cv_demo.py --video path/to/video.mp4
```

Use only footage you have permission to process. Demo flags and
supported inputs should be checked with:

``` bash
python run_cv_demo.py --help
```

The demo may create `demo_trace.jsonl` and `fall_guardian.db` in the
working directory. These are runtime artifacts; inspect them before
sharing and do not commit sensitive records.

## Testing

### Python

Install dependencies and run:

``` bash
python -m pip install -r requirements.txt
python -m pytest -q
```

The tests cover the vision rules, evidence assessment, approval gating,
trace output, event handling, storage behavior, and end-to-end workflow
using synthetic clips and local/fake components where appropriate.

### Node.js components

For the prototype server:

``` bash
cd alexa_mcp_server
npm ci
npm run check
npm test
```

For the JavaScript Lambda component:

``` bash
cd ../aws_backend/lambda
npm ci
npm run check
npm test
```

These commands require Node.js 18 or later. Test success does not
establish that a cloud deployment works or that an external notification
was delivered.

## Evaluation

The recorded synthetic comparison evaluation contains 16 clips:

  Metric                      Recorded result
  ------------------------- -----------------
  True positives                            7
  False positives                           1
  True negatives                            7
  False negatives                           1
  Correct classifications             14 / 16
  Accuracy                              87.5%
  Precision                             87.5%
  Recall / sensitivity                  87.5%
  Specificity                           87.5%
  F1 score                              87.5%

The set includes a missed slow-fall clip and an intentional lie-down
clip incorrectly flagged as a fall. The synthetic comparison set was
reviewed during debugging, so it should not be described as an
independent validation set.

To reproduce the synthetic evaluation, check the current command-line
options and label format, then use the evaluation module. The
repository's documented example is:

``` bash
python -m evaluation.evaluate --labels evaluation/labels_synthetic.csv --out evaluation/results_synthetic
```

No real-world or clinical accuracy is claimed. Evaluation on consented,
independently labelled real footage remains future work.

## Security, privacy, and safety

-   The prototype processes video locally in its documented workflow.
-   Do not record or process people without appropriate consent; avoid
    capturing bystanders.
-   Do not commit `.env` files, API keys, credentials, personal footage,
    or generated incident records.
-   Configure secrets through environment variables or a proper
    secret-management mechanism; never hard-code credentials.
-   Review `SECURITY_REVIEW.md` before enabling network-facing
    components.
-   The approval workflow is not caregiver identity verification.
-   Emergency channels are simulated. A timeout or denial does not
    dispatch help automatically.
-   Do not expose the prototype server publicly without reviewing
    authentication, network binding, configuration, and deployment
    security.

## Limitations

-   The evaluation dataset is small and synthetic.
-   The system can miss some falls and incorrectly flag non-fall
    movements.
-   The current vision approach is rule-based rather than a trained
    deep-learning detector.
-   Results may depend on camera position, lighting, framing, and
    movement.
-   The current workflow is designed around a single visible person and
    a fixed-camera setting.
-   AWS Lambda/DynamoDB deployment and real external notification
    delivery are not verified.
-   The prototype is not a medical device and is not suitable for
    standalone emergency monitoring.

## Future work

Potential next steps include: - Evaluate on larger, independently
labelled datasets with consented real-world footage. - Improve
robustness across camera angles, lighting, and varied movement
patterns. - Add stronger privacy, authentication, and caregiver identity
controls. - Deploy and verify cloud components in a controlled AWS
environment. - Measure performance and failure cases on target
hardware. - Conduct safety and usability evaluation before considering
any real-world use.

These are proposed improvements, not claims about current functionality.

## Contributing

Contributions that improve reproducibility, testing, documentation,
accessibility, or safety are welcome.

1.  Open an issue describing the proposed change.
2.  Create a focused branch.
3.  Add or update tests for behavior changes.
4.  Run the relevant test suites.
5.  Document any new dependencies, configuration, limitations, and
    security implications.
6.  Submit a pull request with a concise explanation of the change.

D
