#!/usr/bin/env python3
"""
End-to-end demo of the vision -> caregiver approval -> workflow loop.

Uses SYNTHETIC clips (a rectangle stands in for a person) and a DEMO emergency
mode, so nothing is sent to anyone. The approval step is answered automatically
unless you pass --ask, in which case you type yes/no at the terminal.

Writes a trace to demo_trace.jsonl in the current directory.
"""
import argparse
import os
import sys
import tempfile

import database_setup as db
from agent.approval_agent import (ApprovalAgent, ConsoleApproval, ConsoleNotifier,
                                  ScriptedApproval, TraceLog, APPROVED, DENIED, TIMEOUT)
from aws.fall_event_handler import handler as store_handler
from aws.local_table import LocalTable
from emergency_response_service import EmergencyResponseService
from vision.evidence import VideoEvidence
from vision.fall_vision import VisionFallDetector
from vision.synthetic_clips import make_clip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--approval', choices=['deny', 'approve', 'timeout', 'ask'], default='deny',
                    help="simulated caregiver decision. Default 'deny': an unattended run takes no action. "
                         "'ask' waits for yes/no at the terminal.")
    ap.add_argument('--ask', action='store_true', help='same as --approval ask')
    ap.add_argument('--trace', default='demo_trace.jsonl')
    ap.add_argument('--ledger-db', default=None,
                    help='store approval decisions in this SQLite file (survives restarts). Default: in memory.')
    ap.add_argument('--video', default=None, help='run on a video file instead of the synthetic clips, e.g. --video my_clip.mp4')
    args = ap.parse_args()

    if os.path.exists(args.trace):
        os.remove(args.trace)
    db.init_database()
    user_id = db.add_user('Demo Patient (synthetic)', 78, None, None)
    tmp = tempfile.mkdtemp()

    if args.video:
        from vision.sources import resolve_video_path, SourceError
        try:
            clips = {'video': resolve_video_path('file:' + args.video)}
        except SourceError as e:
            print(f"ERROR: {e}")
            return 2
    else:
        clips = {'fall': make_clip('fall', os.path.join(tmp, 'fall.mp4')),
                 'walk': make_clip('walk', os.path.join(tmp, 'walk.mp4'))}

    service = EmergencyResponseService(mode='DEMO')
    mode = 'ask' if args.ask else args.approval
    if mode == 'ask':
        approval = ConsoleApproval()
    elif mode == 'timeout':
        approval = ScriptedApproval(TIMEOUT, operator_id='none')
    else:
        approval = ScriptedApproval(APPROVED if mode == 'approve' else DENIED,
                                    operator_id='simulated-operator')
    print(f"APPROVAL SOURCE: {mode.upper()} "
          f"({'simulated decision, no real caregiver' if mode != 'ask' else 'human at terminal'})")
    table = LocalTable()   # stands in for DynamoDB; the real handler runs on AWS
    ledger = None
    if args.ledger_db:
        from agent.approval_ledger import DurableApprovalLedger
        ledger = DurableApprovalLedger(args.ledger_db)
        print(f"LEDGER: durable (SQLite) at {args.ledger_db}")
    agent = ApprovalAgent(service, ConsoleNotifier(), approval, ledger=ledger,
                          trace=TraceLog(args.trace), approval_timeout_s=60,
                          store=lambda payload: store_handler(payload, table=table))

    print("== Step 1: OpenCV 5 vision pipeline ==")
    for name, path in clips.items():
        events, _ = VisionFallDetector().process_video(path)
        print(f"  clip={name:5s} candidate fall events={len(events)}")
        for e in events:
            print(f"    -> t={e.to_dict()['t_s']}s rule fired; sending to agent")
            print("== Step 2-3: agent requests approval, then acts on the decision ==")
            result = agent.handle_vision_event(user_id, e.to_dict(), severity=6,
                                               location=f'Synthetic {name} clip',
                                               evidence=VideoEvidence(path))
            print(f"    agent status={result['status']} workflow={result.get('workflow_status')}")
            print(f"    evidence after event: {result.get('evidence', 'n/a')}")
    service.close()
    print(f"Events stored (local stand-in for DynamoDB): {len(table.items)}")

    print(f"\nTrace written to {args.trace} ({len(open(args.trace).readlines())} steps).")
    print("All clips are synthetic. This run shows the pipeline works end to end; it is not a measure of accuracy.")
    print("Emergency actions were simulated; no one was contacted.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
