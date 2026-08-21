#!/usr/bin/env sh
set -eu

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
python3 -m py_compile "$root/run.py" "$root/harness_runtime.py"
rg -q 'loop_should_continue=loop_should_continue' "$root/run.py"
rg -q 'loop_max_iterations=2' "$root/run.py"
rg -q 'enable_sensitive_data=False' "$root/run.py"
rg -q 'request_digest' "$root/harness_runtime.py"
rg -q 'Never retry ambiguous submissions automatically' "$root/harness_runtime.py"
kubectl kustomize "$root" >/dev/null
printf '%s\n' PYTHON_HARNESS_STATIC_VERIFY_PASS
