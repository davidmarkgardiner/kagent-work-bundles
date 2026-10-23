import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

BUNDLE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit_tools', BUNDLE / 'scripts/audit_tools.py')
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


def write_json(path, value):
    path.write_text(json.dumps(value))


def ledger():
    refs = dict(surface='route', boundary='auth', subsystem='profile/quick/all-in-scope-subsystems', attack_class='access-control')
    return [dict(coverage_id='::'.join(__import__('urllib.parse', fromlist=['quote']).quote(v, safe='-_.~') for v in refs.values()), canonical_refs=refs, surface='Route', boundary='Ownership',
                 subsystem='API', attack_class='Access control', starting_paths=['src/app.py'],
                 ordinary_attack_class_block='ATTACK-CLASSES.md#Access control', selected_companion_blocks=[],
                 excluded_blocks=[], prior_status='new', attempts=[], wave=1, status='covered',
                 agent_id='hunter-1', reviewed_paths=['src/app.py'], local_checks=[dict(agent_id='hunter-1',
                 reviewed_paths=['src/app.py'], invariant='Owner gate', method='source',
                 result='Guard is present', artifact=None)], result_fingerprints=[], unresolved=[])]


def candidate():
    return dict(verdict='needs_validation', fingerprint='missing-owner', title='Missing owner check',
                description='Source appears to omit an owner check', claimed_root_cause='Route omits owner gate',
                trace=[dict(kind=k, file='src/app.py', line=i+1, scope='handler', description='Data propagation')
                       for i, k in enumerate(('entrypoint', 'propagation', 'sink'))],
                evidence=[dict(file='src/app.py', line=3, description='Source calls update')],
                blockers=['Runtime validation is outside source-only scope'],
                validation_plan={'local':'Owner-authorized isolated test required'})


class ToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / 'target'
        self.target.mkdir()
        self.git('init', '-q')
        (self.target / 'src').mkdir()
        (self.target / 'src/app.py').write_text('pass\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
        self.request = dict(target=str(self.target), source_ref=self.git('rev-parse', 'HEAD'),
                            output_dir=str(self.root / 'new-run'), profile='quick', scope_paths=['src'],
                            execution_mode='source-only', model_policy=dict(hunter='host/model-a', verifier='host/model-b',
                            require_different_models=True), agent_budget=12, prior_runs=[], scanner_reports=[])

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output([shutil.which('git'), '-C', str(self.target), *args],
                                       stderr=subprocess.DEVNULL).decode().strip()

    def make_run(self, status='complete'):
        run = self.root / 'run'
        run.mkdir()
        self.request['output_dir'] = str(run)
        for name in tools.ARTIFACTS:
            (run / name).write_text('Source-only partial scope; no confirmed vulnerabilities.\n')
        write_json(run / 'run-metadata.json', dict(target=str(self.target), output_dir=str(run), scope_paths=['src'], profile='quick', budget=12, source_ref=self.request['source_ref'],
                   model_policy=self.request['model_policy'], execution_mode='source-only',
                   execution_policy='sandboxed-source-and-local-only', run_status=status,
                   incomplete_reason='Coverage interrupted' if status == 'incomplete' else None))
        write_json(run / 'findings.json', [])
        write_json(run / 'coverage-ledger.json', ledger())
        receipts = []
        for i, role in enumerate(['recon'] * 4 + ['hunter', 'coverage_critic']):
            agent_id = 'hunter-1' if role == 'hunter' else f'{role}-{i}'
            receipt = f'receipt-{i}.txt'
            (run / receipt).write_text('Controlled test host export fixture; not a live model invocation.\n')
            receipts.append(dict(agent_id=agent_id, role=role, model='host/model-a', context_id=f'context-{i}',
                                 status='completed', receipt_path=receipt, fingerprints=[]))
        write_json(run / 'delegation-receipts.json', receipts)
        return run

    def test_upstream_pin_and_tamper(self):
        tools.verify_upstream()
        bundle = self.root / 'bundle'
        shutil.copytree(BUNDLE / 'upstream', bundle / 'upstream')
        shutil.copy(BUNDLE / 'UPSTREAM.lock.json', bundle)
        (bundle / 'upstream/security-audit/SKILL.md').write_text('tampered')
        with self.assertRaises(ValueError):
            tools.verify_upstream(bundle)

    def test_upstream_symlink_and_modified_lock_fail(self):
        bundle = self.root / 'bundle'
        shutil.copytree(BUNDLE / 'upstream', bundle / 'upstream')
        shutil.copy(BUNDLE / 'UPSTREAM.lock.json', bundle)
        asset = bundle / 'upstream/security-audit/SKILL.md'
        asset.unlink()
        asset.symlink_to(BUNDLE / 'upstream/security-audit/SKILL.md')
        with self.assertRaises(ValueError):
            tools.verify_upstream(bundle)
        value = tools.read_json(bundle / 'UPSTREAM.lock.json')
        value['commit'] = 'a' * 40
        write_json(bundle / 'UPSTREAM.lock.json', value)
        with self.assertRaises(ValueError):
            tools.verify_upstream(bundle)

    def test_clean_preflight_has_no_execution_or_output(self):
        result = tools.preflight(self.request)
        self.assertFalse(result['dirty'])
        self.assertFalse(result['target_code_executed'])
        self.assertFalse(Path(self.request['output_dir']).exists())

    def test_git_target_fsmonitor_is_never_executed(self):
        marker = self.root / 'EXECUTED'
        script = self.root / 'fsmonitor'
        script.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        script.chmod(0o755)
        self.git('config', 'core.fsmonitor', str(script))
        tools.preflight(self.request)
        self.assertFalse(marker.exists())

    def test_git_clean_filter_cannot_execute_even_for_equal_size_change(self):
        source = self.target / 'src/app.py'
        source.write_text('base\n')
        (self.target / '.gitattributes').write_text('src/*.py filter=demo\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'attributes')
        self.request['source_ref'] = self.git('rev-parse', 'HEAD')
        marker = self.root / 'FILTER_EXECUTED'
        script = self.root / 'filter.sh'
        script.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\ncat\n')
        script.chmod(0o755)
        self.git('config', 'filter.demo.clean', str(script))
        source.write_text('fake\n')
        os.utime(source, (source.stat().st_atime, source.stat().st_mtime + 10))
        with self.assertRaisesRegex(ValueError, 'dirty target'):
            tools.preflight(self.request)
        self.request['require_clean'] = False
        self.assertTrue(tools.preflight(self.request)['dirty'])
        self.assertFalse(marker.exists())

    def test_dirty_requires_explicit_acknowledgement(self):
        (self.target / 'src/app.py').write_text('changed\n')
        with self.assertRaises(ValueError):
            tools.preflight(self.request)
        self.request['require_clean'] = False
        self.assertFalse(tools.preflight(self.request)['source_ref_covers_worktree'])

    def test_output_containment_existing_and_symlink(self):
        for value in (self.target / 'out', BUNDLE / 'out', self.root, self.target.parent):
            with self.subTest(path=str(value)), self.assertRaises(ValueError):
                tools.preflight(dict(self.request, output_dir=str(value)))
        link = self.root / 'link'
        link.symlink_to(self.target, target_is_directory=True)
        with self.assertRaises(ValueError):
            tools.preflight(dict(self.request, output_dir=str(link / 'out')))

    def test_invalid_scopes_refs_models_and_budgets(self):
        bad = [('scope_paths', ['../outside']), ('scope_paths', ['.git']), ('scope_paths', []),
               ('source_ref', 'main'), ('source_ref', 'a' * 40), ('agent_budget', 6), ('agent_budget', True),
               ('model_policy', dict(hunter='same', verifier='same', require_different_models=True)),
               ('model_policy', dict(hunter='{{MODEL}}', verifier='x', require_different_models=False))]
        for field, value in bad:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                tools.preflight(dict(self.request, **{field:value}))
        (self.target / 'src/link').symlink_to(self.root)
        with self.assertRaises(ValueError):
            tools.preflight(dict(self.request, scope_paths=['src/link/target']))

    def test_actual_upstream_validators_complete_no_findings(self):
        self.assertEqual(tools.validate_run(self.request, self.make_run()), 0)

    def test_valid_incomplete_and_zero_children_never_complete(self):
        run = self.make_run('incomplete')
        write_json(run / 'delegation-receipts.json', [])
        self.assertEqual(tools.validate_run(self.request, run), 2)
        meta = tools.read_json(run / 'run-metadata.json')
        meta['run_status'] = 'complete'
        write_json(run / 'run-metadata.json', meta)
        with self.assertRaisesRegex(ValueError, 'complete claim contradicts'):
            tools.validate_run(self.request, run)

    def test_receipt_context_reuse_symlink_and_traversal(self):
        run = self.make_run()
        original = tools.read_json(run / 'delegation-receipts.json')
        for field, value in [('context_id', original[0]['context_id']), ('receipt_path', '../outside')]:
            records = copy.deepcopy(original)
            records[1][field] = value
            write_json(run / 'delegation-receipts.json', records)
            with self.assertRaises(ValueError):
                tools.validate_run(self.request, run)
        write_json(run / 'delegation-receipts.json', original)
        (run / original[0]['receipt_path']).unlink()
        (run / original[0]['receipt_path']).symlink_to(run / original[1]['receipt_path'])
        with self.assertRaises(ValueError):
            tools.validate_run(self.request, run)

    def test_candidate_requires_fresh_verifier_and_schema_forbids_severity(self):
        run = self.make_run()
        finding = candidate()
        write_json(run / 'findings.json', [finding])
        coverage = ledger()
        coverage[0].update(status='candidate', result_fingerprints=[finding['fingerprint']])
        write_json(run / 'coverage-ledger.json', coverage)
        with self.assertRaises(ValueError):
            tools.validate_run(self.request, run)
        receipts = tools.read_json(run / 'delegation-receipts.json')
        receipts[4]['fingerprints'] = [finding['fingerprint']]
        (run / 'verifier.txt').write_text('Controlled fixture export')
        receipts.append(dict(agent_id='verifier-1', role='candidate_verifier', model='host/model-b',
            context_id='fresh-verifier', status='completed', receipt_path='verifier.txt', fingerprints=[finding['fingerprint']]))
        write_json(run / 'delegation-receipts.json', receipts)
        self.assertEqual(tools.validate_run(self.request, run), 0)
        finding['severity'] = 'critical'
        write_json(run / 'findings.json', [finding])
        with self.assertRaisesRegex(ValueError, 'actual upstream'):
            tools.validate_run(self.request, run)

    def test_standard_requires_distinct_final_critic_and_verifier(self):
        run = self.make_run()
        finding = candidate()
        coverage = ledger()
        coverage[0].update(status='candidate', result_fingerprints=[finding['fingerprint']])
        write_json(run / 'coverage-ledger.json', coverage)
        write_json(run / 'findings.json', [finding])
        meta = tools.read_json(run / 'run-metadata.json')
        meta['profile'] = 'standard'
        self.request['profile'] = 'standard'
        write_json(run / 'run-metadata.json', meta)
        receipts = tools.read_json(run / 'delegation-receipts.json')
        receipts[4]['fingerprints'] = [finding['fingerprint']]
        for role in ('candidate_verifier', 'final_critic', 'final_verifier'):
            with self.assertRaisesRegex(ValueError, 'complete claim contradicts'):
                tools.validate_run(self.request, run)
            (run / f'{role}.txt').write_text('Controlled fixture export')
            receipts.append(dict(agent_id=role, role=role, model='host/model-b', context_id=role,
                status='completed', receipt_path=f'{role}.txt',
                fingerprints=[] if role == 'final_critic' else [finding['fingerprint']]))
            write_json(run / 'delegation-receipts.json', receipts)
        self.assertEqual(tools.validate_run(self.request, run), 0)

    def test_request_binding_rejects_source_model_and_budget_mismatch(self):
        run = self.make_run()
        original = tools.read_json(run / 'run-metadata.json')
        for key, value in [('source_ref', 'a' * 40), ('budget', 11), ('scope_paths', ['different']),
                           ('model_policy', dict(hunter='fake', verifier='fake', require_different_models=False))]:
            meta = copy.deepcopy(original)
            meta[key] = value
            write_json(run / 'run-metadata.json', meta)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'differs from explicit request'):
                tools.validate_run(self.request, run)

    def test_execution_policy_is_required_and_cannot_conflict(self):
        run = self.make_run()
        original = tools.read_json(run / 'run-metadata.json')
        for value in (None, 'production-live'):
            meta = copy.deepcopy(original)
            if value is None:
                del meta['execution_policy']
            else:
                meta['execution_policy'] = value
            write_json(run / 'run-metadata.json', meta)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'execution_policy'):
                tools.validate_run(self.request, run)

    def test_unverified_candidate_is_valid_only_as_incomplete_cli_exit_two(self):
        run = self.make_run('incomplete')
        coverage = ledger()
        coverage[0].update(status='candidate', result_fingerprints=['pending-candidate'])
        write_json(run / 'coverage-ledger.json', coverage)
        receipts = tools.read_json(run / 'delegation-receipts.json')
        receipts[4]['fingerprints'] = ['pending-candidate']
        write_json(run / 'delegation-receipts.json', receipts)
        request_path = self.root / 'request.json'
        write_json(request_path, self.request)
        result = subprocess.run([shutil.which('python3'), '-B', str(BUNDLE / 'scripts/validate-run.py'),
                                str(request_path), str(run)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertTrue(result.stdout.startswith('INCOMPLETE:'))

    def test_quick_wave_and_subsystem_cannot_drift(self):
        run = self.make_run()
        original = ledger()
        for field, value in [('wave', 2), ('canonical_refs', dict(original[0]['canonical_refs'], subsystem='api'))]:
            coverage = copy.deepcopy(original)
            coverage[0][field] = value
            if field == 'canonical_refs':
                coverage[0]['coverage_id'] = '::'.join(value.values())
            write_json(run / 'coverage-ledger.json', coverage)
            with self.assertRaisesRegex(ValueError, 'quick ledger'):
                tools.validate_run(self.request, run)

    def test_hunter_must_own_coverage_and_dirty_run_is_incomplete(self):
        run = self.make_run()
        coverage = ledger()
        coverage[0]['agent_id'] = 'recon-0'
        coverage[0]['local_checks'][0]['agent_id'] = 'recon-0'
        write_json(run / 'coverage-ledger.json', coverage)
        with self.assertRaisesRegex(ValueError, 'complete claim contradicts'):
            tools.validate_run(self.request, run)
        write_json(run / 'coverage-ledger.json', ledger())
        (self.target / 'src/app.py').write_text('dirty\n')
        self.request['require_clean'] = False
        with self.assertRaisesRegex(ValueError, 'complete claim contradicts'):
            tools.validate_run(self.request, run)
        meta = tools.read_json(run / 'run-metadata.json')
        meta.update(run_status='incomplete', incomplete_reason='Dirty worktree cannot be pinned')
        write_json(run / 'run-metadata.json', meta)
        self.assertEqual(tools.validate_run(self.request, run), 2)

    def test_confirmed_records_forbidden(self):
        run = self.make_run()
        value = candidate()
        confirmed = dict(verdict='confirmed', fingerprint=value['fingerprint'], title=value['title'],
            description=value['description'], root_cause=value['claimed_root_cause'], intended_behavior='Owner must match',
            trace=value['trace'], evidence=value['evidence'], conditions=[], execution=dict(attacker_perspective='User',
            payloads=['Other ID'], instructions=['Call route'], observed_result='Other object changed'),
            remediation={'strategy':'Check owner'}, severity=dict(likelihood=dict(score='medium', reason='Reachable'),
            impact=dict(score='medium', reason='Data changes'), overall_severity='medium'),
            confidence=dict(score='high', reason='Observed'))
        write_json(run / 'findings.json', [confirmed])
        with self.assertRaisesRegex(ValueError, 'source-only run cannot contain confirmed'):
            tools.validate_run(self.request, run)

    def test_missing_or_malformed_artifacts_and_sizes(self):
        run = self.make_run()
        (run / 'REPORT.md').unlink()
        with self.assertRaises(OSError):
            tools.validate_run(self.request, run)
        (run / 'REPORT.md').write_bytes(b'x' * (tools.MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            tools.validate_run(self.request, run)

    def test_checksum_manifest_is_required_and_complete(self):
        bundle = self.root / 'bundle'
        bundle.mkdir()
        asset = bundle / 'README.md'
        asset.write_text('fixture')
        with self.assertRaises(OSError):
            tools.verify_checksums(bundle)
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        (bundle / 'CHECKSUMS.sha256').write_text(digest + '  README.md\n')
        tools.verify_checksums(bundle)
        (bundle / 'unexpected').write_text('unexpected')
        with self.assertRaises(ValueError):
            tools.verify_checksums(bundle)

    def test_optional_reviewer_cannot_gain_tools_or_skills(self):
        bundle = self.root / 'bundle'
        (bundle / 'manifests').mkdir(parents=True)
        doc = dict(apiVersion='kagent.dev/v1alpha2', kind='Agent', metadata={'labels':{
            'platform.com/evidence-only':'true', 'platform.com/type':'triage'}},
            spec=dict(type='Declarative', declarative=dict(modelConfig='default', systemMessage='Review evidence', tools=[])))
        path = bundle / 'manifests/agent.yaml'
        write_json(path, doc)
        tools.verify_manifest(bundle)
        for field, value in [('tools', [{'type':'McpServer'}]), ('skills', ['security-audit']), ('runtime', {})]:
            mutated = copy.deepcopy(doc)
            mutated['spec']['declarative'][field] = value
            write_json(path, mutated)
            with self.assertRaises(ValueError):
                tools.verify_manifest(bundle)


if __name__ == '__main__':
    unittest.main()
