# Baseline report

Recorded at the start of this pass on the hardened archive (`fall-guardian-HARDENED.zip`), before any code change.

## Environment

| Item | Value |
|---|---|
| Python | 3.12.3 |
| OpenCV | 5.0.0 (`opencv-python-headless` 5.0.0.93); only OpenCV distribution installed |
| NumPy | 2.2.6 |
| Node.js | v22.22.2 |
| CPU | Intel Xeon 2.10 GHz, 1 logical CPU, no GPU |
| OS | Ubuntu 24.04.4 LTS, Linux 6.18 |

The earlier review reported OpenCV 4.13.0 in its test environment. This baseline was re-run in a clean virtual environment, and the runtime import reports OpenCV 5.0.0, so that earlier concern does not apply to this run.

## Commands and results

| Check | Command | Result |
|---|---|---|
| Python tests | `python -m pytest -q` | exit 0; 157 passed, 2 xfailed (expected failures) |
| Seven-clip synthetic evaluation | `python -m evaluation.evaluate --labels evaluation/labels_synthetic.csv --out ...` | TP 2, FP 0, TN 3, FN 2 |
| Metric check from raw counts | script | precision 1.000, recall 0.500, specificity 1.000, F1 0.667 (agrees with the reported values) |
| Node (HTTP API) | `npm ci && npm test` | 17 pass, 0 fail (see note below) |
| Node (Lambda) | `npm ci && npm test` | 7 pass, 0 fail |
| Dependency audit (production) | `npm audit --omit=dev` | 0 vulnerabilities |

Note on Node: the earlier review could not run these tests because dependencies were unavailable. In this environment, `npm ci` from the committed lockfiles installs successfully and all Node tests pass.

## Failures identified in the baseline

### Missed falls (both synthetic)

The earlier explanations for these two misses were partly wrong. Per-frame traces show the actual mechanisms:

**`slow_fall`**: the upright-to-lying transition took 0.33 s, inside the 1.0 s window, so the transition window was not the cause. The lying run was 1.27 s, short of the 1.5 s hold. At about 7.7 s the lying box jumped from aspect 0.34 to 1.03 while the centroid stayed at 0.773, consistent with background absorption resetting the hold timer.

**`fall_then_up`**: the 1.5 s hold was reached at 7.2 s, but the drop condition was re-evaluated on each frame. The centroid rose slightly as the person began to stand, so the drop condition failed on the exact frame the hold was met.

### Other defects found during this pass

- Zero-frame video: a file that opens but decodes no frames returned "no events", which reads as a normal result. (Fixed in the change pass.)

## Limitations of this baseline

- Seven synthetic clips; no real footage; no split is possible at this size.
- Metrics above describe the baseline detector only.
- Node test results are for the lockfile-pinned versions in this environment.
