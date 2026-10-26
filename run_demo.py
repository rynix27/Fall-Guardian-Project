#!/usr/bin/env python3
"""
Fall Guardian - local end-to-end DEMO.

Runs synthetic sensor data through the threshold PROTOTYPE detector and the
emergency workflow in DEMO mode. Every outward action is SIMULATED: no SMS is
sent, no 911 call is placed, no smart-home device is operated.

The demo writes to the database named by FALL_GUARDIAN_DB (default:
fall_guardian.db in the current directory). Delete that file to reset the demo.
"""
import sys

import database_setup as db
from emergency_response_service import EmergencyResponseService


def banner(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main() -> int:
    banner("FALL GUARDIAN - LOCAL DEMO (SIMULATED ACTIONS ONLY)")
    print("Detector: threshold PROTOTYPE, not a trained or clinically validated model.")

    db.init_database()
    user_id = db.add_user("Margaret Smith", 75, "+1-555-0199", "margaret.demo@example.test")
    print(f"\nDemo user created: ID={user_id} (Margaret Smith, 75)")

    accel = [15.2, 14.8, 16.1]
    heart_rate = 95
    print(f"Synthetic reading: accelerometer={accel}, heart_rate={heart_rate}")

    service = EmergencyResponseService(mode='DEMO', contacts=['+1-555-0100'])
    try:
        r = service.detect_fall(user_id, accel, heart_rate)
    finally:
        service.close()

    banner("RESULT")
    print(f"Detection status:   {r['detection_status']}")
    print(f"Prototype score:    {r['prototype_score']} (uncalibrated heuristic, not a probability)")
    print(f"Estimated severity: {r['severity']}/10")
    print(f"Incident ID:        {r['incident_id']}")
    print(f"Workflow status:    {r['status']}")
    print(f"Response time:      {r['response_time_ms']} ms")
    print("\nChannel outcomes:")
    for name, ch in r['channels'].items():
        print(f"  {name:22s} {ch['status']:14s} {ch['detail']}")

    ok = r['detection_status'] == 'FALL_DETECTED' and r['status'] == 'SIMULATED_ONLY'
    banner("DEMO " + ("COMPLETED" if ok else "DID NOT COMPLETE AS EXPECTED"))
    print("Nothing was contacted: all channels are simulated.")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
