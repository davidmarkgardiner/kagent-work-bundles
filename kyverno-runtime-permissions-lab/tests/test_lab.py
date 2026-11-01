import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'lab.py'
spec = importlib.util.spec_from_file_location('lab', MODULE)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def sample_data(namespace='application'):
    report = {'metadata': {'name': 'pod-report', 'namespace': namespace},
              'scope': {'uid': 'current-pod-uid', 'kind': 'Pod', 'name': 'pod', 'namespace': namespace},
              'results': [{'policy': lab.POLICY, 'rule': rule, 'result': 'pass',
                           'properties': {'process': 'background scan'},
                           'timestamp': {'seconds': int(lab.dt.datetime.now(lab.dt.timezone.utc).timestamp())}, 'message': 'rule passed'} for rule in lab.RULES]}
    return {'namespaces': {'items': [{'metadata': {'name': namespace, 'uid': 'ns-uid', 'labels': {}}}]},
            'pods': {'items': [{'kind': 'Pod', 'metadata': {'name': 'pod', 'namespace': namespace,
                                                        'uid': 'current-pod-uid', 'creationTimestamp': '2026-11-01T11:00:00Z'}, 'spec': {}}]},
            'deployments': {'items': []}, 'policy': lab.read(lab.ROOT / 'policies/audit.json'),
            'reports': {'items': [report]}, 'config': {'data': {}}, 'webhooks': {'items': [{'webhooks': [{'name': 'validate.kyverno.svc-fail', 'failurePolicy': 'Fail', 'rules': [{'apiGroups': ['*'], 'resources': ['*', '*/*'], 'operations': ['CREATE', 'UPDATE']}]}]}]}, 'exceptions': {'items': []}}


class CoverageTests(unittest.TestCase):
    def summary(self, data, available=True):
        return lab.build_coverage(data, {'available': available})[0]['summary']

    def test_all_six_current_uid_background_passes(self):
        result = self.summary(sample_data())
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['pass'], 6)

    def test_no_report_is_not_compliant(self):
        data = sample_data()
        data['reports']['items'] = []
        result = self.summary(data)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['missing'], 6)

    def test_replaced_pod_uid_does_not_inherit_old_results(self):
        data = sample_data()
        data['pods']['items'][0]['metadata']['uid'] = 'replacement-uid'
        self.assertEqual(self.summary(data)['missing'], 6)

    def test_failure_counts_checks_and_resources_separately(self):
        data = sample_data()
        for result in data['reports']['items'][0]['results'][:2]:
            result['result'] = 'fail'
        summary = self.summary(data)
        self.assertEqual(summary['status'], 'fail')
        self.assertEqual(summary['fail'], 2)
        self.assertEqual(summary['failingResources'], 1)

    def test_excluded_namespace_is_never_pass(self):
        summary = self.summary(sample_data('kube-system'))
        self.assertEqual(summary['status'], 'excluded')
        self.assertEqual(summary['skip'], 6)
        self.assertEqual(summary['pass'], 0)

    def test_mixed_pass_and_missing_is_not_compliant(self):
        data = sample_data()
        data['reports']['items'][0]['results'].pop()
        summary = self.summary(data)
        self.assertEqual((summary['status'], summary['pass'], summary['missing']), ('incomplete', 5, 1))

    def test_controller_failure_cannot_be_green(self):
        self.assertEqual(self.summary(sample_data(), available=False)['status'], 'unavailable')

    def test_missing_policy_cannot_be_green(self):
        data = sample_data()
        data['policy'] = None
        self.assertEqual(self.summary(data)['status'], 'unavailable')

    def test_empty_namespace_is_visible_and_not_pass(self):
        data = sample_data()
        data['pods']['items'] = []
        self.assertEqual(self.summary(data)['status'], 'empty')

    def test_every_nonpass_result_prevents_green(self):
        for result in ('warn', 'error', 'skip'):
            with self.subTest(result=result):
                data = sample_data()
                data['reports']['items'][0]['results'][0]['result'] = result
                self.assertEqual(self.summary(data)['status'], 'incomplete')

    def test_admission_results_do_not_substitute_background_scan(self):
        data = sample_data()
        for result in data['reports']['items'][0]['results']:
            result['properties']['process'] = 'admission review'
        self.assertEqual(self.summary(data)['missing'], 6)

    def test_resource_list_report_form_is_supported(self):
        data = sample_data()
        report = data['reports']['items'][0]
        scope = report.pop('scope')
        for result in report['results']:
            result['resources'] = [scope]
        self.assertEqual(self.summary(data)['status'], 'pass')

    def test_old_timestamp_is_stale(self):
        data = sample_data()
        data['reports']['items'][0]['results'][0]['timestamp'] = {'seconds': 1}
        self.assertEqual(self.summary(data)['stale'], 1)
        self.assertEqual(self.summary(data)['status'], 'incomplete')

    def test_report_age_limit_marks_old_pass_stale(self):
        data = sample_data()
        for result in data['reports']['items'][0]['results']:
            result['timestamp']['seconds'] -= 301
        self.assertEqual(self.summary(data)['stale'], 6)
        self.assertEqual(self.summary(data)['status'], 'incomplete')

    def test_wildcard_resource_filter_prevents_green(self):
        data = sample_data()
        data['config']['data']['resourceFilters'] = '[*/*,app*,*]'
        row = lab.build_coverage(data, {'available': True})[0]
        self.assertTrue(row['filters'])
        self.assertEqual(row['summary']['status'], 'incomplete')

    def test_enforce_without_pod_webhook_cannot_be_green(self):
        data = sample_data(lab.DEMO[0])
        data['policy'] = lab.read(lab.ROOT / 'policies/enforce-demo.json')
        data['webhooks'] = {'items': []}
        self.assertEqual(self.summary(data)['status'], 'unavailable')

    def test_enforce_requires_ephemeral_update_webhook(self):
        data = sample_data(lab.DEMO[0])
        data['policy'] = lab.read(lab.ROOT / 'policies/enforce-demo.json')
        data['webhooks']['items'][0]['webhooks'][0]['rules'][0]['resources'] = ['pods']
        self.assertEqual(self.summary(data)['status'], 'unavailable')

    def test_pods_wildcard_subresource_is_supported(self):
        data = sample_data(lab.DEMO[0])
        data['policy'] = lab.read(lab.ROOT / 'policies/enforce-demo.json')
        data['webhooks']['items'][0]['webhooks'][0]['rules'][0]['resources'] = ['pods', 'pods/*']
        self.assertEqual(self.summary(data)['status'], 'pass')

    def test_cleanup_webhook_does_not_prove_pod_validation(self):
        data = sample_data(lab.DEMO[0])
        data['policy'] = lab.read(lab.ROOT / 'policies/enforce-demo.json')
        data['webhooks']['items'][0]['webhooks'][0]['name'] = 'kyverno-cleanup-controller.kyverno.svc'
        self.assertEqual(self.summary(data)['status'], 'unavailable')

    def test_future_timestamp_is_stale(self):
        data = sample_data()
        data['reports']['items'][0]['results'][0]['timestamp']['seconds'] += 120
        self.assertEqual(self.summary(data)['stale'], 1)
        self.assertEqual(self.summary(data)['status'], 'incomplete')

    def test_scope_drift_prevents_green(self):
        data = sample_data()
        data['policy']['spec']['rules'][0]['match']['any'][0]['resources']['kinds'] = ['Service']
        self.assertEqual(self.summary(data)['status'], 'unavailable')

    def test_actual_modes_show_audit_and_enforce(self):
        data = sample_data(lab.DEMO[0])
        data['policy'] = lab.read(lab.ROOT / 'policies/enforce-demo.json')
        row = lab.build_coverage(data, {'available': True})[0]
        self.assertEqual(row['effectiveMode'], 'Enforce')
        self.assertEqual(set(row['ruleModes'].values()), {'Enforce'})


class SafetyTests(unittest.TestCase):
    def test_specimen_is_gated_and_unbound(self):
        pod = lab.read(lab.ROOT / 'fixtures/seed/gated-noncompliant.json')
        lab.assert_gated(pod)
        for field in ('nodeName', 'schedulingGates', 'nodeSelector'):
            bad = copy.deepcopy(pod)
            bad['spec'][field] = 'node' if field == 'nodeName' else []
            with self.assertRaises(RuntimeError):
                lab.assert_gated(bad)

    def test_denial_requires_kyverno_policy_and_expected_rule(self):
        class FakeKube:
            context = 'offline-test'
            calls = []

            def get(self, args):
                if args[0] == 'clusterpolicy':
                    data = lab.read(lab.ROOT / 'policies/enforce-demo.json')
                elif args[0] == 'namespace':
                    data = {'items': []}
                else:
                    data = lab.read(lab.ROOT / 'fixtures/seed/compliant-pod.json')
                return data, {'exitCode': 0}

            def run(self, args, body):
                self.calls.append(args)
                return {'exitCode': 1, 'stdout': '', 'stderr': 'Forbidden by RBAC', 'argv': args}

        kube = FakeKube()
        with tempfile.TemporaryDirectory() as directory:
            results = lab.verify_dry_run(kube, Path(directory))
        self.assertEqual(len(results), 34)
        self.assertTrue(all(not r['passed'] for r in results))
        self.assertEqual(len(kube.calls), 34)
        for args in kube.calls:
            if args[0] == 'replace':
                self.assertIn('--raw', args)
                self.assertTrue(any('/ephemeralcontainers?dryRun=All' in arg for arg in args))
            else:
                self.assertEqual(args[0], 'create')
                self.assertIn('--dry-run=server', args)

    def test_namespace_boundaries_have_explicit_dryrun_cases(self):
        cases = {case['name']: case for case in lab.admission_cases()}
        self.assertEqual(cases['noncompliant-namespace-compliant']['namespace'], lab.DEMO[1])
        self.assertEqual(cases['noncompliant-namespace-sys-admin']['expected'], 'deny')
        self.assertEqual(cases['audit-sys-admin']['namespace'], 'default')
        self.assertEqual(cases['audit-sys-admin']['expected'], 'allow')
        self.assertEqual(cases['excluded-sys-admin']['namespace'], 'policy-reporter')
        self.assertEqual(cases['excluded-sys-admin']['expected'], 'allow')

    def test_ephemeral_is_update_only(self):
        for case in lab.admission_cases():
            if case['object'].get('spec', {}).get('ephemeralContainers'):
                self.assertEqual(case['operation'], 'ephemeral-update')


if __name__ == '__main__':
    unittest.main()
