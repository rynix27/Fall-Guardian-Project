"""
Clip-level evaluation of the vision fall detector.

Input: a labels CSV with columns  path,label,dataset
  label = 1 for a fall clip, 0 for a non-fall clip
  dataset = 'synthetic' or 'real' (so results are never mixed up)

Output: a JSON results file and a Markdown summary listing every error.

Usage:
  python -m evaluation.evaluate --labels evaluation/labels_synthetic.csv --out evaluation/results_synthetic
"""
import argparse
import csv
import json
import os
from datetime import datetime, timezone

from vision.fall_vision import VisionFallDetector


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


def evaluate(rows):
    tp = fp = tn = fn = 0
    details = []
    for r in rows:
        events, _ = VisionFallDetector().process_video(r['path'])
        predicted = 1 if events else 0
        label = int(r['label'])
        if label == 1 and predicted == 1:
            tp += 1; outcome = 'TP'
        elif label == 0 and predicted == 1:
            fp += 1; outcome = 'FP'
        elif label == 1 and predicted == 0:
            fn += 1; outcome = 'FN'
        else:
            tn += 1; outcome = 'TN'
        details.append({
            'path': r['path'], 'dataset': r.get('dataset', 'unknown'),
            'label': label, 'predicted': predicted, 'outcome': outcome,
            'events': [e.to_dict() for e in events],
        })
    n = len(rows)
    sens = tp / (tp + fn) if (tp + fn) else None
    spec = tn / (tn + fp) if (tn + fp) else None
    prec = tp / (tp + fp) if (tp + fp) else None
    return {
        'n_clips': n, 'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn,
        'sensitivity': sens, 'specificity': spec, 'precision': prec,
        'sensitivity_95ci': wilson(tp, tp + fn), 'specificity_95ci': wilson(tn, tn + fp),
        'clips': details,
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'note': ('Very small sample. Intervals are wide; these numbers describe this clip set only '
                 'and do not estimate real-world performance.'),
    }


def _fmt(x):
    return 'n/a' if x is None else f"{x:.2f}"


def write_markdown(res, path, title):
    lines = [f"# {title}", "", res['note'], "",
             f"Clips: {res['n_clips']}  |  TP {res['TP']}  FP {res['FP']}  TN {res['TN']}  FN {res['FN']}", "",
             f"- Sensitivity: {_fmt(res['sensitivity'])}  (95% CI {_fmt(res['sensitivity_95ci'][0])}-{_fmt(res['sensitivity_95ci'][1])})",
             f"- Specificity: {_fmt(res['specificity'])}  (95% CI {_fmt(res['specificity_95ci'][0])}-{_fmt(res['specificity_95ci'][1])})",
             f"- Precision: {_fmt(res['precision'])}", "",
             "## Per-clip results", "", "| Clip | Label | Predicted | Outcome |", "|---|---|---|---|"]
    for c in res['clips']:
        lines.append(f"| {os.path.basename(c['path'])} | {c['label']} | {c['predicted']} | {c['outcome']} |")
    errors = [c for c in res['clips'] if c['outcome'] in ('FP', 'FN')]
    lines += ["", "## Errors (failure cases)", ""]
    if not errors:
        lines.append("None in this set.")
    for c in errors:
        lines.append(f"- **{c['outcome']}**: {os.path.basename(c['path'])} (label {c['label']}, predicted {c['predicted']})")
    with open(path, 'w') as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', required=True)
    ap.add_argument('--out', required=True, help='output path prefix (no extension)')
    args = ap.parse_args()
    with open(args.labels, newline='') as f:
        rows = list(csv.DictReader(f))
    res = evaluate(rows)
    with open(args.out + '.json', 'w') as f:
        json.dump(res, f, indent=2)
    write_markdown(res, args.out + '.md', 'Vision fall detector: evaluation results')
    print(f"clips={res['n_clips']} TP={res['TP']} FP={res['FP']} TN={res['TN']} FN={res['FN']}")
    print(f"wrote {args.out}.json and {args.out}.md")


if __name__ == '__main__':
    main()
