import json
from pathlib import Path
import tempfile
import threading
import unittest

from flow_telemetry import FlowTelemetry


class FlowTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.run = {'runId': 'demo-current', 'workspace': self.directory.name,
                    '_call': {'mode': 'execute'}, 'secret': 'do-not-export'}
        self.records, self.now = [], 1000
        self.telemetry = self.make()

    def make(self, **kwargs):
        telemetry = FlowTelemetry('http://127.0.0.1:4318',
            transport=kwargs.pop('transport', lambda endpoint, signal, value: self.records.append((signal, value))),
            clock_ns=lambda: self.now, **kwargs)
        self.addCleanup(telemetry.close)
        return telemetry

    def drain(self, telemetry=None):
        (telemetry or self.telemetry)._queue.join()

    def test_actual_start_pending_and_terminal_span_use_original_timestamps(self):
        carrier = self.telemetry.begin(self.run, 'triage')
        self.drain()
        self.assertEqual([signal for signal, _ in self.records], ['logs'])
        self.assertRegex(carrier, r'^00-[0-9a-f]{32}-[0-9a-f]{16}-01$')
        context = Path(self.directory.name) / '.flow-telemetry-triage.json'
        self.assertEqual(context.stat().st_mode & 0o777, 0o600)
        self.now = 2000
        self.telemetry.observe(self.run, 'triage', {'status': 'pending', 'private': 'do-not-export'})
        self.drain()
        self.assertEqual([signal for signal, _ in self.records], ['logs', 'logs'])
        self.assertFalse(json.loads(context.read_text())['ended'])
        self.telemetry.observe(self.run, 'triage', {'status': 'pending'})
        self.assertEqual(carrier, self.telemetry.begin(self.run, 'triage'))
        self.drain()
        self.assertEqual(len(self.records), 2)
        self.now = 3000
        self.telemetry.observe(self.run, 'triage', {'status': 'completed'})
        self.drain()
        span = self.records[-1][1]['resourceSpans'][0]['scopeSpans'][0]['spans'][0]
        self.assertEqual((span['startTimeUnixNano'], span['endTimeUnixNano']), ('1000', '3000'))
        self.assertEqual(span['traceId'], carrier.split('-')[1])
        self.assertEqual(span['kind'], 3)
        self.assertTrue(json.loads(context.read_text())['ended'])
        self.assertNotIn('do-not-export', json.dumps(self.records))

    def test_native_continuation_gets_a_distinct_actual_context(self):
        original=self.telemetry.begin(self.run,'triage')
        self.telemetry.observe(self.run,'triage',{'status':'blocked'});self.drain()
        path=Path(self.directory.name)/'.flow-telemetry-triage.json';old=path.read_bytes()
        current=self.telemetry.begin(self.run,'triage_continuation')
        self.telemetry.observe(self.run,'triage_continuation',{'status':'pending'});self.drain()
        self.assertNotEqual(original,current);self.assertEqual(path.read_bytes(),old)
        self.assertIn('triage_continuation',json.dumps(self.records))

    def test_classification_followup_keeps_suppressed_context_and_records_actual_new_operation(self):
        first=self.telemetry.begin(self.run,'classify')
        self.telemetry.observe(self.run,'classify',{'status':'suppressed'});self.drain()
        path=Path(self.directory.name)/'.flow-telemetry-classify.json';before=path.read_bytes()
        followup=self.telemetry.begin(self.run,'classification_followup');self.drain()
        self.assertNotEqual(first,followup)
        self.telemetry.observe(self.run,'classification_followup',{'status':'completed'});self.drain()
        self.assertEqual(path.read_bytes(),before)
        span=self.records[-1][1]['resourceSpans'][0]['scopeSpans'][0]['spans'][0]
        self.assertEqual(span['name'],'demo.classification_followup')
        self.assertEqual(span['traceId'],followup.split('-')[1])

    def test_recheck_has_distinct_context_and_preserves_failed_observation(self):
        first=self.telemetry.begin(self.run,'observe_fault')
        self.telemetry.observe(self.run,'observe_fault',{'status':'blocked'});self.drain()
        original=Path(self.directory.name)/'.flow-telemetry-observe_fault.json';before=original.read_bytes()
        recheck=self.telemetry.begin(self.run,'recheck_fault');self.drain()
        self.assertNotEqual(first,recheck)
        self.telemetry.observe(self.run,'recheck_fault',{'status':'completed'});self.drain()
        self.assertEqual(original.read_bytes(),before)
        self.assertTrue((Path(self.directory.name)/'.flow-telemetry-recheck_fault.json').exists())

    def test_restart_preserves_open_context_without_reexporting_start_or_pending(self):
        carrier = self.telemetry.begin(self.run, 'review')
        self.telemetry.observe(self.run, 'review', {'status': 'pending'})
        self.drain()
        restarted = self.make()
        self.run['_call']['mode'] = 'observe'
        self.now = 4000
        self.assertEqual(carrier, restarted.begin(self.run, 'review'))
        restarted.observe(self.run, 'review', {'status': 'pending'})
        self.drain(restarted)
        self.assertEqual(len(self.records), 2)
        restarted.observe(self.run, 'review', {'status': 'completed'})
        self.drain(restarted)
        span = self.records[-1][1]['resourceSpans'][0]['scopeSpans'][0]['spans'][0]
        self.assertEqual(span['startTimeUnixNano'], '1000')
        self.assertIsNone(restarted.begin(self.run, 'review'))

    def test_no_retroactive_telemetry_for_existing_uninstrumented_intents(self):
        self.run['_call']['mode'] = 'observe'
        self.assertIsNone(self.telemetry.begin(self.run, 'triage'))
        self.telemetry.observe(self.run, 'triage', {'status': 'completed'})
        self.drain()
        self.assertEqual(self.records, [])
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_metadata_allowlist_never_serializes_results_or_error_text(self):
        self.run.update(data={'token': 'secret-value'}, url='https://private.invalid')
        first = self.telemetry.begin(self.run, 'classify')
        self.telemetry.observe(self.run, 'classify', {'status': 'completed', 'prompt': 'secret-value'})
        second = self.telemetry.begin(self.run, 'dispatch')
        self.telemetry.observe(self.run, 'dispatch', error=ValueError('private-error-payload'))
        self.drain()
        serialized = json.dumps(self.records)
        for forbidden in ('secret-value', 'private-error-payload', 'private.invalid', 'prompt', 'token'):
            self.assertNotIn(forbidden, serialized)
        self.assertNotEqual(first.split('-')[1], second.split('-')[1])
        for signal, envelope in self.records:
            resource = envelope['resourceLogs' if signal == 'logs' else 'resourceSpans'][0]
            self.assertEqual(resource['resource']['attributes'][0]['value']['stringValue'], 'kyverno-demo-controller')
            scope = resource['scopeLogs' if signal == 'logs' else 'scopeSpans'][0]
            item = scope['logRecords' if signal == 'logs' else 'spans'][0]
            attrs = {x['key']: x['value']['stringValue'] for x in item['attributes']}
            self.assertEqual(set(attrs), {'flow.run.id', 'flow.demo.step', 'flow.demo.state', 'flow.evidence.source',
                                          'flow.component', 'flow.workflow', 'flow.result'})
            self.assertEqual(attrs['flow.component'], 'client')
            self.assertEqual(attrs['flow.workflow'], 'kyverno-demo.' + attrs['flow.demo.step'])
            self.assertEqual(attrs['flow.result'], attrs['flow.demo.state'])

    def test_export_failure_does_not_repeat_or_raise(self):
        calls = []
        def fail(*args):
            calls.append(args)
            raise OSError('private failed endpoint')
        telemetry = self.make(transport=fail)
        telemetry.begin(self.run, 'classify')
        telemetry.observe(self.run, 'classify', {'status': 'completed'})
        self.drain(telemetry)
        self.assertEqual(len(calls), 3)
        self.assertEqual(telemetry.snapshot()['failures'], 3)
        telemetry.observe(self.run, 'classify', {'status': 'completed'})
        self.assertIsNone(telemetry.begin(self.run, 'classify'))
        self.assertEqual(len(calls), 3)

    def test_bounded_queue_drops_without_blocking_actual_work(self):
        entered, release = threading.Event(), threading.Event()
        def wait(*args):
            entered.set()
            release.wait(2)
        telemetry = self.make(transport=wait, queue_size=1)
        telemetry.begin(self.run, 'prepare')
        self.assertTrue(entered.wait(1))
        telemetry.begin(self.run, 'inject_fault')
        telemetry.begin(self.run, 'classify')
        self.assertEqual(telemetry.snapshot()['dropped'], 1)
        release.set()
        self.drain(telemetry)

    def test_optional_default_is_disabled_and_origins_reject_credentials(self):
        telemetry = FlowTelemetry()
        self.assertIsNone(telemetry.begin(self.run, 'classify'))
        self.assertEqual(telemetry.snapshot()['enabled'], False)
        for endpoint in ('http://token@localhost:4318', 'http://localhost:4318/?token=secret',
                         'http://localhost:4318/v1/traces', 'file:///tmp/otel', 'http://localhost/#fragment'):
            with self.assertRaises(ValueError):
                FlowTelemetry(endpoint)


if __name__ == '__main__':
    unittest.main()
