# Evaluation report

**Read first.** Every number here comes from synthetic clips in which a rectangle stands in
for a person. The clips are generated, not recorded. They show how the rules behave on these
inputs. They are not evidence of real-world accuracy. No real footage has been evaluated.

## 1. Datasets

| Set | Clips | Positives | Negatives | Use |
|---|---|---|---|---|
| **Development** (`evaluation/labels_synthetic.csv`) | 7 | 4 | 3 | Used to diagnose failures and design the fixes. Not independent evidence. |
| **Comparison set** (`evaluation/labels_heldout.csv`) | 16 | 8 | 8 | Each of 8 scenarios at person scale 0.7 and 1.3, with new random seeds. Reviewed during debugging; not independent validation. Still synthetic. |

Scenarios: fall, slow_fall, fall_then_up, long_lie, sit_down, bend, walk, and in the held-out
set also intentional_lie (a deliberate slow lie-down; label 0).

Development and held-out splits are not independent of the design process in the same way
real-world splits would be. The held-out set is more informative because it uses different
person sizes and seeds that the design did not see, but it is still one synthetic generator
and one geometry model.

## 2. Method

- Each clip is processed by `VisionFallDetector` with default configuration.
- A clip is predicted positive if at least one event is emitted.
- Metrics are clip-level. Precision, recall, specificity and F1 use the standard formulas;
  zero denominators are reported as undefined.
- 95% intervals are Wilson score intervals.
- Commands:
  `python -m evaluation.evaluate --labels evaluation/labels_synthetic.csv --out evaluation/results_synthetic`
  `python -m evaluation.evaluate --labels evaluation/labels_heldout.csv --out evaluation/results_heldout`

## 3. Results

### Development set (7 clips)

| | Before the change | After the change |
|---|---|---|
| TP / FP / TN / FN | 2 / 0 / 3 / 2 | 4 / 0 / 3 / 0 |
| Recall (sensitivity) | 0.50 (CI 0.15–0.85) | 1.00 (CI 0.51–1.00) |
| Specificity | 1.00 (CI 0.44–1.00) | 1.00 (CI 0.44–1.00) |
| Precision | 1.00 | 1.00 |
| F1 | 0.667 | 1.000 |

The "after" column is in-sample: the change was made after reading these clips. Read it as a
check that the fix works on the clips that motivated it, not as a measure of performance.

### Synthetic comparison set (16 clips; reviewed during debugging)

| | Before the change | After the change |
|---|---|---|
| TP / FP / TN / FN | 4 / 0 / 8 / 4 | 7 / 1 / 7 / 1 |
| Recall | 0.50 (CI 0.22–0.79) | 0.875 (CI 0.53–0.98) |
| Specificity | 1.00 (CI 0.68–1.00) | 0.875 (CI 0.53–0.98) |
| Precision | 1.00 | 0.875 |
| F1 | 0.667 | 0.875 |

Held-out misses after the change: `slow_fall` at scale 0.7.
Held-out false alarm after the change: `intentional_lie` at scale 1.3.

**Interpretation.** On held-out clips, the change improves recall from 0.50 to 0.875. It also
introduces one false alarm on a deliberate lie-down, so specificity falls from 1.00 to 0.875.
With 8 positives and 8 negatives, the confidence intervals are wide and overlap considerably.
The direction of the change is consistent across both sets, but neither set supports a claim
about real-world performance.

### Confusion matrices

Held-out, after the change:

|  | Actual fall | Actual non-fall |
|---|---|---|
| Predicted fall | TP = 7 | FP = 1 (intentional_lie, scale 1.3) |
| Predicted non-fall | FN = 1 (slow_fall, scale 0.7) | TN = 7 |

## 4. What the change does, and its trade-off

Two general fixes to the state machine:

1. **Grace period (0.5 s).** A brief rise in the lying box's aspect ratio does not end a lying
   episode if the centroid stays low. This addresses background absorption.
2. **Latched drop.** The largest centroid drop within an episode is kept, so a small rise while
   standing up cannot cancel a condition that was already satisfied.

Trade-off: a deliberate, slow lie-down has the same posture sequence as a slow fall. The
detector cannot distinguish them from posture alone. The intentional_lie false alarm at scale
1.3 is this trade-off made visible. It is recorded as a strict expected failure
(`tests/test_known_failures.py`).

The two fixes were applied together. Their individual contributions were not separated by an ablation run, so the held-out result should be read as the effect of the combined change.

Both fixes were guided by the development clips. The comparison results document behavior across different generated sizes and seeds, but because the set was reviewed during debugging, they do not establish independent generalization.

## 5. Detection latency

Latency = time from the first lying frame in a lying episode to the emitted event. With the
1.5 s hold, the event is emitted about 1.53 s after the first lying frame on the reference clip.
Latency is bounded below by the hold time by design. Not measured separately for every clip.

## 6. Not reported, and why

- **False alarms per hour:** not measurable. Clips are a few seconds long, and no continuous
  footage was evaluated.
- **Per-scenario results beyond the scenario list:** the datasets contain one clip per scenario
  per scale, so per-scenario percentages would be single observations.
- **Independent validation/test split:** not available. The 16-clip comparison set was reviewed during debugging and must not be described as an independent check.
- **Real-footage results:** none exist. `evaluation/labels_real.csv` is an empty template.

## 7. Performance (measured on this machine)

Intel Xeon 2.10 GHz, 1 logical CPU, no GPU, OpenCV 5.0.0, Python 3.12.3. Classic OpenCV only;
no neural network, so no inference time.

| Input | Median FPS | Median ms/frame | Peak memory | Event latency |
|---|---|---|---|---|
| 320×240 synthetic | 762 | 1.31 | 60 MB | 1.53 s |
| 1280×720 (upscaled from 320×240) | 329 | 3.04 | 73 MB | 1.53 s |

Earlier runs on the same machine gave 812 and 304 FPS. Run-to-run variation on this shared
single-core machine is roughly ±10%, so treat these as indicative, not precise. The 720p clip
measures decode and resize cost on upscaled content, not detection quality on real 720p footage.

## 8. Limitations

- Synthetic clips with a rectangle standing in for a person. Arms, legs, clothing, lighting,
  clutter, and camera motion are not modelled.
- Single person, fixed camera, good lighting assumed.
- Posture is inferred from one blob's aspect ratio and centroid. Intentional and accidental
  lying look the same.
- Background absorption affects long motionless periods; the grace period reduces but does not
  remove this effect.
- The rules were designed after viewing the development clips.

## 9. Reproduce

```bash
python -m evaluation.evaluate --labels evaluation/labels_synthetic.csv --out evaluation/results_synthetic
python -m evaluation.evaluate --labels evaluation/labels_heldout.csv --out evaluation/results_heldout
python -m evaluation.benchmark --clip evaluation/clips_synthetic/synthetic_fall.mp4 --runs 5 --out evaluation/benchmark_results.json
```

Archived pre-change results: `evaluation/archive/dev_before_change.json` and
`evaluation/archive/heldout_before_change.json`. Computed metrics: `evaluation/metrics_summary.json`.
