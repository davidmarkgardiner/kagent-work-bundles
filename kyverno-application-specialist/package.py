#!/usr/bin/env python3
"""Package the connected recovery source using the OTel bundle's existing allowlist."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    source = root.parent / 'otel-agent-flow'
    if args.output.exists() or args.output.with_suffix(args.output.suffix + '.sha256').exists():
        parser.error('Choose a fresh output path; preserve earlier packages')
    names = ['README.md', 'OFFICE-HANDOFF.md', '.dockerignore', 'KYVERNO-KNOWLEDGE.md', 'VALIDATION.md',
             'run-lab-proof.py', 'package.py', 'test_package.py']
    files = [root / name for name in names] + sorted((root / 'fixtures').glob('*.yaml'))
    live_names = ['README.md', 'DESIGN.md', 'core.py', 'admission.py', 'runtime.py',
                  'config.example.json', 'test_runtime.py', 'collect_probe.py',
                  'test_collect_probe.py', 'classifier.py', 'test_classifier.py',
                  'CLASSIFIER.md', 'viewer.py', 'native_dispatch.py',
                  'test_native_dispatch.py', 'NATIVE-DISPATCH.md', 'test_viewer.py',
                  'pending_view.py', 'test_pending_view.py', 'DASHBOARD-FLOW.md',
                  'flow_controller.py', 'test_flow_controller.py', 'flow_server.py', 'test_flow_server.py',
                  'flow_telemetry.py', 'test_flow_telemetry.py', 'demo_flow.py', 'test_demo_flow.py',
                  'gitlab_lifecycle.py', 'test_gitlab_lifecycle.py', 'lab_adapter.py', 'test_lab_adapter.py']
    files += [root / 'live' / name for name in live_names]
    files += [root / 'live/budget' / name for name in
              ['README.md', 'DESIGN.md', 'budget_proxy.py', 'test_budget_proxy.py']]
    files += sorted((root / 'skills').rglob('*.md'))
    office_names = ['WORK-AGENT-PROMPT.md', 'Dockerfile.runtime', 'settings.example.json', 'ssh-argv.example.json',
                    'agent-bindings.example.json', 'runtime.example.yaml', 'budget.example.yaml',
                    'budget-config.example.json', 'flux.example.yaml', 'policy-faulty.example.json',
                    'gitops/.gitlab-ci.yml', 'gitops/ci/test_policy.py',
                    'gitops/deploy/kustomization.yaml', 'gitops/deploy/policy.json',
                    'gitops/deploy/application.json', 'gitops/deploy/service.json']
    files += [root / 'office' / name for name in office_names]
    plan = root.parent / 'docs/plans/kyverno-application-specialist.md'
    if not plan.is_file():
        plan = root.parents[1] / 'docs/plans/kyverno-application-specialist.md'
    for path in files + [plan]:
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f'Missing or symlinked source file: {path.name}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    hashes = []
    with tempfile.TemporaryDirectory() as temporary:
        upstream_zip = Path(temporary) / 'otel-source.zip'
        subprocess.run([sys.executable, '-B', str(source / 'scripts/package.py'), '--output', str(upstream_zip)],
                       check=True, stdout=subprocess.DEVNULL)
        with zipfile.ZipFile(upstream_zip) as upstream, zipfile.ZipFile(args.output, 'x', zipfile.ZIP_DEFLATED) as archive:
            def write(name, data):
                archive.writestr(name, data)
                hashes.append(hashlib.sha256(data).hexdigest() + '  ' + name)

            for entry in upstream.infolist():
                write('work-agent-bundles/' + entry.filename, upstream.read(entry))
            for path in files:
                write('work-agent-bundles/kyverno-application-specialist/' + path.relative_to(root).as_posix(), path.read_bytes())
            write('docs/plans/kyverno-application-specialist.md', plan.read_bytes())
            write('START-HERE.md', b'# Office handoff for the Kyverno recovery demonstration\n\nStart with work-agent-bundles/kyverno-application-specialist/OFFICE-HANDOFF.md. It identifies office inputs, native API compatibility, reference resources, GitOps/CI files and target acceptance checks.\n\nThe latest fresh lab run completed dashboard human approval, native Kagent merge, exact-revision GitOps and measured application recovery, separate native verification and verified issue closure. Numbers 1 through 9 open stage summaries. The global OTel observation cap can evict early-stage component evidence; durable controller history remains.\n\nOffice deployment is not yet validated. The examples require private environment binding and review. This source package contains no credentials, filled private settings, raw task receipts, native CLI binaries or OCI images.\n')
            archive.writestr('SHA256SUMS', '\n'.join(hashes) + '\n')
    checksum = hashlib.sha256(args.output.read_bytes()).hexdigest()
    with args.output.with_suffix(args.output.suffix + '.sha256').open('x') as stream:
        stream.write(checksum + '  ' + args.output.name + '\n')
    print(str(args.output.resolve()))
    print('SHA-256 ' + checksum)


if __name__ == '__main__':
    main()
