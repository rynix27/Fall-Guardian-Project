"""
Measures the vision pipeline on THIS machine. Reports only what was measured.

Writes evaluation/benchmark_results.json with hardware details, timings, and
peak memory. No model inference is involved (classic OpenCV only), so no
inference time is reported.

Usage: python -m evaluation.benchmark --clip evaluation/clips_synthetic/synthetic_fall.mp4 --runs 5
"""
import argparse
import json
import os
import platform
import resource
import statistics
import time

import cv2

from vision.fall_vision import VisionFallDetector, STATE_UPRIGHT

LYING_AT_OR_BELOW = 0.9


def cpu_info():
    model = 'unknown'
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                if line.lower().startswith('model name'):
                    model = line.split(':', 1)[1].strip()
                    break
    except OSError:
        pass
    return {'cpu_model': model, 'logical_cpus': os.cpu_count(),
            'platform': platform.platform(), 'python': platform.python_version(),
            'opencv': cv2.__version__, 'gpu': 'none used (CPU only)'}


def run_once(path):
    det = VisionFallDetector()
    cap = cv2.VideoCapture(path)
    fps_src = cap.get(cv2.CAP_PROP_FPS) or 15.0
    cap.release()
    t0 = time.perf_counter()
    events, trace = det.process_video(path, keep_trace=True)
    elapsed = time.perf_counter() - t0
    frames = len(trace)

    # event latency: from the first frame the body was lying (per trace) to the event
    first_lying = next((r.t_s for r in trace if r.aspect is not None and r.aspect <= LYING_AT_OR_BELOW), None)
    latency = (events[0].t_s - first_lying) if (events and first_lying is not None) else None
    return {'frames': frames, 'elapsed_s': elapsed, 'fps': frames / elapsed,
            'ms_per_frame': 1000 * elapsed / frames, 'source_fps': fps_src,
            'events': len(events), 'event_latency_s': latency}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clip', required=True)
    ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--out', default='evaluation/benchmark_results.json')
    args = ap.parse_args()

    runs = [run_once(args.clip) for _ in range(args.runs)]
    fps = [r['fps'] for r in runs]
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # Linux: KB -> MB
    result = {
        'clip': os.path.basename(args.clip),
        'clip_resolution': None,
        'runs': args.runs,
        'median_fps': statistics.median(fps),
        'min_fps': min(fps), 'max_fps': max(fps),
        'median_ms_per_frame': statistics.median(r['ms_per_frame'] for r in runs),
        'peak_process_memory_mb': round(peak_mb, 1),
        'events_per_run': [r['events'] for r in runs],
        'event_latency_s': runs[0]['event_latency_s'],
        'hardware': cpu_info(),
        'note': ('Synthetic 320x240 clip, classic OpenCV only, CPU only. '
                 'Numbers describe this machine and this clip, not a general benchmark.'),
    }
    cap = cv2.VideoCapture(args.clip)
    result['clip_resolution'] = f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
    cap.release()
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: result[k] for k in ('clip', 'clip_resolution', 'median_fps',
                                              'median_ms_per_frame', 'peak_process_memory_mb',
                                              'event_latency_s')}, indent=2))


if __name__ == '__main__':
    main()
