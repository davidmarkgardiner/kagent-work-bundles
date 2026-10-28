import copy
import unittest

from native_acceptance import evaluate, reported_compliance


def envelope():
    import json
    import pathlib
    fixture = json.loads((pathlib.Path(__file__).resolve().parent.parent / 'data/fixture.json').read_text())
    entities = [n['value'] for n in fixture['nodes'] if n['environment'] == 'production' and n['category'] == 'entity']
    views = [n['value'] for n in fixture['nodes'] if n['environment'] == 'production' and n['category'] == 'view']
    edges = [e['value'] for e in fixture['edges'] if e['environment'] == 'production']
    context = {'status': 'supported', 'source': 'fixture-v1', 'entities': entities, 'views': views, 'relationships': edges, 'scope': {'environments': ['production'], 'groupings': ['commerce', 'governance', 'platform'], 'result_count': 10, 'complete': True}, 'truncated': False, 'limitations': []}
    return {'task': {'status': {'state': 'TASK_STATE_COMPLETED'}, 'history': [{'role': 'ROLE_AGENT', 'parts': [{'metadata': {'kagent.dev/a2a/part-type': 'function_call'}, 'data': {'name': 'get_graph_context'}}, {'metadata': {'kagent.dev/a2a/part-type': 'function_response'}, 'data': {'name': 'get_graph_context', 'response': context}}]}], 'artifacts': [{'parts': [{'text': 'fixture-v1 production checkout=compliant; metrics=non_compliant. prod:checkout assessed_by prod:checkout-check.'}]}]}}


class NativeAcceptanceTests(unittest.TestCase):
    def test_equivalent_workload_answer_formats_and_wrong_status(self):
        for answer in ('checkout=compliant', '**workload checkout**: compliant.', 'The checkout workload is compliant.'):
            self.assertTrue(reported_compliance(answer, 'checkout', 'compliant'))
        for answer in ('checkout=non_compliant', 'checkout: not compliant', 'checkout-check: compliant', 'checkout is not compliant'):
            self.assertFalse(reported_compliance(answer, 'checkout', 'compliant'))
        self.assertTrue(reported_compliance('**workload metrics**: non_compliant.', 'metrics', 'non_compliant'))
        data = envelope()
        data['task']['artifacts'][0]['parts'][0]['text'] = 'Source fixture-v1. Scope production. **workload checkout**: compliant. **workload metrics**: non_compliant. prod:checkout assessed_by prod:checkout-check.'
        self.assertTrue(evaluate(data, 'supported', 'production', 10)[3])

    def test_out_of_domain_refusal_is_honest_without_querying_data(self):
        answer = 'I cannot provide weather information because it is outside the scope of graph metadata. Source: none. Scope: unspecified.'
        data = {'task': {'status': {'state': 'TASK_STATE_COMPLETED'}, 'history': [], 'artifacts': [{'parts': [{'text': answer}]}]}}
        self.assertTrue(evaluate(data, 'unsupported', None, 0, allow_local_refusal=True)[3])
        self.assertFalse(evaluate(data, 'supported', 'production', 10)[3])
        self.assertFalse(evaluate(data, 'ambiguous', None, 0)[3])
        for wrong in (answer.replace('Source: none', 'Source: fixture-v1'), answer + ' It is sunny.', answer.replace('cannot', 'can').replace('outside the scope', 'inside the scope')):
            changed = copy.deepcopy(data)
            changed['task']['artifacts'][0]['parts'][0]['text'] = wrong
            self.assertFalse(evaluate(changed, 'unsupported', None, 0, allow_local_refusal=True)[3])
        changed = copy.deepcopy(data)
        changed['task']['history'] = [{'role': 'ROLE_AGENT', 'parts': [{'functionCall': {'name': 'arbitrary_sql'}}]}]
        self.assertFalse(evaluate(changed, 'unsupported', None, 0, allow_local_refusal=True)[3])

    def test_relationship_question_checks_edges_without_demanding_unasked_status_prose(self):
        data = envelope()
        good = 'Coverage complete. prod:checkout assessed_by prod:checkout-check; prod:metrics assessed_by prod:metrics-check. Source: fixture-v1. Scope: production.'
        data['task']['artifacts'][0]['parts'][0]['text'] = good
        self.assertTrue(evaluate(data, 'supported', 'production', 10)[3])
        prefix = 'Source: fixture-v1. Scope: production. `assessed_by`: prod:checkout -> prod:checkout-check; `contains`: prod:payments -> prod:checkout.'
        data['task']['artifacts'][0]['parts'][0]['text'] = prefix
        self.assertTrue(evaluate(data, 'supported', 'production', 10)[3])
        for bad in (good.replace('prod:checkout-check', 'prod:metrics-check'), good + ' prod:invented contains prod:checkout.', good + ' checkout is non_compliant.', prefix.replace('prod:checkout-check', 'prod:metrics-check')):
            data['task']['artifacts'][0]['parts'][0]['text'] = bad
            self.assertFalse(evaluate(data, 'supported', 'production', 10)[3])

    def test_completed_requires_matching_trace_and_facts(self):
        self.assertTrue(evaluate(envelope(), 'supported', 'production', 10)[3])
        for mutate in ('no_call', 'wrong_scope', 'false_completion', 'no_source', 'wrong_tool'):
            data = copy.deepcopy(envelope())
            parts = data['task']['history'][0]['parts']
            if mutate == 'no_call':
                parts.pop(0)
            elif mutate == 'wrong_tool':
                parts[0]['data']['name'] = 'arbitrary_sql'
            elif mutate == 'wrong_scope':
                parts[1]['data']['response']['scope']['environments'] = ['development']
            elif mutate == 'false_completion':
                data['task']['status']['state'] = 'TASK_STATE_FAILED'
            elif mutate == 'no_source':
                data['task']['artifacts'][0]['parts'][0]['text'] = 'production checkout metrics'
            with self.subTest(mutate=mutate):
                self.assertFalse(evaluate(data, 'supported', 'production', 10)[3])


if __name__ == '__main__':
    unittest.main()
