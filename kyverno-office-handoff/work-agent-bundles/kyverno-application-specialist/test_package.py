import ast
import hashlib
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import yaml


ROOT = Path(__file__).resolve().parent


class OfficePackageTests(unittest.TestCase):
    def test_runtime_image_copy_set_imports_all_operator_pod_dependencies(self):
        code=ast.parse((ROOT/'live/lab_adapter.py').read_text())
        pod_code=next(node.value.value for node in code.body if isinstance(node,ast.Assign)
                      and any(isinstance(target,ast.Name) and target.id=='POD_CODE' for target in node.targets))
        imports=set()
        for node in ast.walk(ast.parse(pod_code)):
            if isinstance(node,ast.Import):imports.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node,ast.ImportFrom) and node.module:imports.add(node.module.split('.')[0])
        local={name for name in imports if (ROOT/'live'/f'{name}.py').exists()}
        with tempfile.TemporaryDirectory() as temporary:
            app=Path(temporary)
            for line in (ROOT/'office/Dockerfile.runtime').read_text().splitlines():
                if line.startswith('COPY '):
                    for source in shlex.split(line)[1:-1]:shutil.copy2(ROOT/source,app/Path(source).name)
            result=subprocess.run([sys.executable,'-I','-B','-c',
                'import sys;sys.path.insert(0,".");import '+','.join(sorted(local|{'budget_proxy'}))],
                cwd=app,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_clean_extraction_imports_checksums_and_repackages(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            archive_path = target / 'office.zip'
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'package.py'),
                                     '--output', str(archive_path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(archive_path.with_suffix('.zip.sha256').is_file())
            with zipfile.ZipFile(archive_path) as archive:
                self.assertIsNone(archive.testzip())
                lines = archive.read('SHA256SUMS').decode().splitlines()
                self.assertEqual(len(lines), len(archive.namelist()) - 1)
                for line in lines:
                    expected, name = line.split('  ', 1)
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)
                start = archive.read('START-HERE.md').decode()
                self.assertIn('OFFICE-HANDOFF.md', start)
                self.assertNotIn('still awaits a fresh', start)
                archive.extractall(target / 'extracted')
            exported = target / 'extracted/work-agent-bundles/kyverno-application-specialist'
            imported = subprocess.run([sys.executable, '-B', '-c',
                                       'import flow_server, flow_controller, lab_adapter, runtime'],
                                      cwd=exported / 'live', capture_output=True, text=True)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            repacked = subprocess.run([sys.executable, '-B', str(exported / 'package.py'),
                                       '--output', str(target / 'repacked.zip')],
                                      cwd=target / 'extracted', capture_output=True, text=True)
            self.assertEqual(repacked.returncode, 0, repacked.stderr)
            with zipfile.ZipFile(target / 'repacked.zip') as archive:
                self.assertEqual(archive.read('SHA256SUMS').decode().splitlines(), lines)

    def test_reference_resources_preserve_runtime_contract_and_read_only_permissions(self):
        documents = list(yaml.safe_load_all((ROOT / 'office/runtime.example.yaml').read_text()))
        deployment = next(doc for doc in documents if doc['kind'] == 'Deployment')
        pod = deployment['spec']['template']['spec']
        runtime = pod['containers'][0]
        self.assertIn('--data', runtime['args'])
        self.assertEqual(runtime['args'][runtime['args'].index('--data') + 1], '/data/runs/office-bootstrap')
        projected = next(volume['projected'] for volume in pod['volumes'] if volume['name'] == 'config')
        config_map = next(source['configMap'] for source in projected['sources'] if 'configMap' in source)
        self.assertEqual(config_map['name'], '{{RUNTIME_DEPLOYMENT}}-config')
        for document in documents:
            if document['kind'] == 'Role':
                self.assertTrue(all(set(rule['verbs']) <= {'get', 'list'} for rule in document['rules']))
                self.assertTrue(all('secrets' not in rule['resources'] for rule in document['rules']))
        bindings = json.loads((ROOT / 'office/agent-bindings.example.json').read_text())
        self.assertNotIn('merge_policy_fix', bindings['specialist']['allowed_tools'])
        self.assertEqual(bindings['executor']['credential_role'], 'investigator')
        self.assertEqual(bindings['executor']['allowed_tools'], ['merge_dashboard_approved_fix', 'verify_recovery'])
        budget_docs = list(yaml.safe_load_all((ROOT / 'office/budget.example.yaml').read_text()))
        budget_pod = next(doc for doc in budget_docs if doc['kind'] == 'Deployment')['spec']['template']['spec']
        self.assertFalse(budget_pod['automountServiceAccountToken'])

    def test_office_ci_accepts_healthy_contract_and_rejects_the_fault(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / 'repo'
            shutil.copytree(ROOT / 'office/gitops', repo)
            for path in repo.rglob('*'):
                if path.is_file():
                    path.write_text(path.read_text().replace('{{DEMO_NAMESPACE}}', 'office-demo'))
            script = [sys.executable, '-B', 'ci/test_policy.py']
            healthy = subprocess.run(script, cwd=repo, capture_output=True, text=True)
            self.assertEqual(healthy.returncode, 0, healthy.stdout + healthy.stderr)
            report = ET.parse(repo / 'policy-report.xml').getroot()
            self.assertEqual(report.attrib['failures'], '0')
            self.assertEqual({case.attrib['name'] for case in report},
                             {'valid-image-admitted', 'invalid-image-denied', 'enforcement-retained', 'scope-retained'})
            faulty = (ROOT / 'office/policy-faulty.example.json').read_text().replace('{{DEMO_NAMESPACE}}', 'office-demo')
            (repo / 'deploy/policy.json').write_text(faulty)
            failed = subprocess.run(script, cwd=repo, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            report = ET.parse(repo / 'policy-report.xml').getroot()
            self.assertTrue(any(case.attrib['name'] == 'valid-image-admitted' and case.find('failure') is not None for case in report))


if __name__ == '__main__':
    unittest.main()
