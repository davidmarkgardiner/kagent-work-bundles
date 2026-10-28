#!/usr/bin/env python3
"""Verify copied source and run offline tests. Does not contact a cluster."""
import json
from pathlib import Path
import subprocess
import sys
import package

package.verify_snapshot()
root = Path(__file__).resolve().parent
source = root / 'implementation/platform/skills-registry'
groups = [(source, ['test_controller.py', 'test_knowledge.py', 'test_portability.py']),
          (source / 'native', ['test_artifacts.py', 'test_native.py']),
          (source / 'golden', ['test_checks.py']),
          (source / 'knowledge', ['test_evidence.py', 'test_runner.py']),
          (source / 'hosted', ['test_onboarding.py', 'test_acceptance.py', 'test_fixed_profile.py', 'test_fixed_mcp.py', 'test_trace_bootstrap.py', 'test_combined_acceptance.py', 'test_ordinary_viewer.py']),
          (root / 'implementation/work-agent-bundles/otel-agent-flow', ['test_telemetry.py', 'test_ui.py', 'test_onboarding.py', 'test_ordinary_telemetry.py', 'test_ordinary_onboarding.py']),
          (root, ['test_package.py','test_private_install.py'])]
for cwd, tests in groups:
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', *tests], cwd=cwd)
    if result.returncode:
        sys.exit(result.returncode)
print(json.dumps({'mode': 'offlineVerification', 'groupsPassed': len(groups), 'targetVerified': False}))
