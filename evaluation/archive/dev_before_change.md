# Vision fall detector: evaluation results

Very small sample. Intervals are wide; these numbers describe this clip set only and do not estimate real-world performance.

Clips: 7  |  TP 2  FP 0  TN 3  FN 2

- Sensitivity: 0.50  (95% CI 0.15-0.85)
- Specificity: 1.00  (95% CI 0.44-1.00)
- Precision: 1.00

## Per-clip results

| Clip | Label | Predicted | Outcome |
|---|---|---|---|
| synthetic_fall.mp4 | 1 | 1 | TP |
| synthetic_slow_fall.mp4 | 1 | 0 | FN |
| synthetic_fall_then_up.mp4 | 1 | 0 | FN |
| synthetic_long_lie.mp4 | 1 | 1 | TP |
| synthetic_sit_down.mp4 | 0 | 0 | TN |
| synthetic_bend.mp4 | 0 | 0 | TN |
| synthetic_walk.mp4 | 0 | 0 | TN |

## Errors (failure cases)

- **FN**: synthetic_slow_fall.mp4 (label 1, predicted 0)
- **FN**: synthetic_fall_then_up.mp4 (label 1, predicted 0)
