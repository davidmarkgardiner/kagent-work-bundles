#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v kyverno >/dev/null
command -v python3 >/dev/null
out=$(mktemp -d "${TMPDIR:-/tmp}/istio-mutation-repro.XXXXXXXX")
mkdir "$out/bad" "$out/restored"
kyverno version
kyverno apply fixtures/bad-policy.yaml --resource fixtures/peerauthentication.yaml -o "$out/bad" --remove-color
kyverno apply fixtures/restored-policy.yaml --resource "$out/bad/repro-peer-mtls-mutated.yaml" -o "$out/restored" --remove-color
# Check the real CLI output without requiring a Python YAML dependency.
python3 - "$out" <<'PY'
from pathlib import Path
import re
import sys
root = Path(sys.argv[1])
for directory, expected in [('bad', '1-23'), ('restored', '1-29')]:
    result = (root / directory / 'repro-peer-mtls-mutated.yaml').read_text()
    actual = re.search(r'istio\.io/rev:\s*["\x27]?([^\s"\x27]+)', result)
    assert actual and actual.group(1) == expected, result
    print(f'PASS {directory}: revision={expected}')
PY
echo "Synthetic output: $out. No cluster calls were made."
