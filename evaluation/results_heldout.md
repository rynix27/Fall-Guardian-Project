# Vision fall detector: evaluation results

Very small sample. Intervals are wide; these numbers describe this clip set only and do not estimate real-world performance.

Clips: 16  |  TP 7  FP 1  TN 7  FN 1

- Sensitivity: 0.88  (95% CI 0.53-0.98)
- Specificity: 0.88  (95% CI 0.53-0.98)
- Precision: 0.88

## Per-clip results

| Clip | Label | Predicted | Outcome |
|---|---|---|---|
| fall_s07.mp4 | 1 | 1 | TP |
| slow_fall_s07.mp4 | 1 | 0 | FN |
| fall_then_up_s07.mp4 | 1 | 1 | TP |
| long_lie_s07.mp4 | 1 | 1 | TP |
| intentional_lie_s07.mp4 | 0 | 0 | TN |
| sit_down_s07.mp4 | 0 | 0 | TN |
| bend_s07.mp4 | 0 | 0 | TN |
| walk_s07.mp4 | 0 | 0 | TN |
| fall_s13.mp4 | 1 | 1 | TP |
| slow_fall_s13.mp4 | 1 | 1 | TP |
| fall_then_up_s13.mp4 | 1 | 1 | TP |
| long_lie_s13.mp4 | 1 | 1 | TP |
| intentional_lie_s13.mp4 | 0 | 1 | FP |
| sit_down_s13.mp4 | 0 | 0 | TN |
| bend_s13.mp4 | 0 | 0 | TN |
| walk_s13.mp4 | 0 | 0 | TN |

## Errors (failure cases)

- **FN**: slow_fall_s07.mp4 (label 1, predicted 0)
- **FP**: intentional_lie_s13.mp4 (label 0, predicted 1)
