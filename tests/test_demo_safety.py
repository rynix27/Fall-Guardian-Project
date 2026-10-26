"""
The CLI demo must not dispatch anything by default. These tests run the real
script in a temporary working directory and read the trace it writes.
"""
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_demo(tmp_path, *args):
    env = {**os.environ, 'PYTHONPATH': REPO}
    trace = tmp_path / 'trace.jsonl'
    proc = subprocess.run(
        [sys.executable, os.path.join(REPO, 'run_cv_demo.py'), '--trace', str(trace), *args],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    steps = [json.loads(l) for l in trace.read_text().splitlines()] if trace.exists() else []
    return proc, steps


def test_default_demo_takes_no_action(tmp_path):
    proc, steps = run_demo(tmp_path)
    assert proc.returncode == 0, proc.stderr
    names = [s['step'] for s in steps]
    assert 'APPROVAL_REQUESTED' in names
    assert 'WORKFLOW_RESULT' not in names
    assert 'STORE_RESULT' not in names
    assert 'APPROVAL SOURCE: DENY' in proc.stdout


def test_explicit_approve_runs_simulated_workflow_and_says_so(tmp_path):
    proc, steps = run_demo(tmp_path, '--approval', 'approve')
    assert proc.returncode == 0, proc.stderr
    assert 'WORKFLOW_RESULT' in [s['step'] for s in steps]
    assert 'simulated decision, no real caregiver' in proc.stdout


def test_timeout_mode_dispatches_nothing(tmp_path):
    proc, steps = run_demo(tmp_path, '--approval', 'timeout')
    assert proc.returncode == 0, proc.stderr
    names = [s['step'] for s in steps]
    assert 'NO_RESPONSE' in names
    assert 'WORKFLOW_RESULT' not in names


def test_durable_ledger_option_writes_a_database_file(tmp_path):
    db = tmp_path / 'approvals.db'
    proc, _ = run_demo(tmp_path, '--approval', 'deny', '--ledger-db', str(db))
    assert proc.returncode == 0, proc.stderr
    assert db.exists() and db.stat().st_size > 0
    assert 'LEDGER: durable' in proc.stdout
