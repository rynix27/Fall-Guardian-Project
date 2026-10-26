#!/usr/bin/env bash
# Pre-submission check. Run from the project root on YOUR machine.
# It runs the tests, both evaluations, the demos, the Node suites, and a secret scan.
set -u
fail=0
step() { echo; echo "== $1 =="; }
run() { if "$@"; then echo "PASS: $*"; else echo "FAIL: $*"; fail=1; fi; }

step "Python tests"
run python -m pytest -q

step "Demos (simulated only)"
run python run_cv_demo.py --approval deny --trace /tmp/fg_deny.jsonl
run python run_cv_demo.py --approval approve --trace /tmp/fg_approve.jsonl

step "Synthetic evaluation (development and held-out)"
run python -m evaluation.evaluate --labels evaluation/labels_synthetic.csv --out /tmp/fg_dev
run python -m evaluation.evaluate --labels evaluation/labels_heldout.csv --out /tmp/fg_heldout

if [ -s evaluation/labels_real.csv ] && [ "$(wc -l < evaluation/labels_real.csv)" -gt 1 ]; then
  step "Real-footage evaluation"
  run python -m evaluation.evaluate --labels evaluation/labels_real.csv --out evaluation/results_real
else
  echo; echo "NOTE: evaluation/labels_real.csv is empty. Real-footage evaluation not run."
fi

step "Node: HTTP API and Lambda"
(cd alexa_mcp_server && run npm ci --no-audit --no-fund && run npm test)
(cd aws_backend/lambda && run npm ci --no-audit --no-fund && run npm test)

step "Secret scan"
if grep -rnIE "AKIA[0-9A-Z]{16}|BEGIN (RSA|EC|OPENSSH) PRIVATE|sk-ant-|xox[baprs]-" . --exclude-dir=node_modules --exclude-dir=venv --exclude-dir=.git --exclude=presubmit_check.sh >/dev/null; then
  echo "FAIL: possible secret found (see matches above)"; fail=1
else
  echo "PASS: no secret patterns found"
fi

echo
if [ $fail -eq 0 ]; then echo "PRE-SUBMISSION CHECK: ALL CHECKS PASSED"; else echo "PRE-SUBMISSION CHECK: FAILURES - do not submit yet"; fi
exit $fail
