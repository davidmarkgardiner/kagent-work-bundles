import json
from pathlib import Path

import pytest

from app.models import ContextRequest
from app.retrieval import retrieve
from comparison.pilot import ARMS, Case, measurements, model_request, render, restore_tables, schedule, score, SafeError


def cases():
    return [Case.model_validate(c) for c in json.loads((Path(__file__).parent.parent / 'comparison/cases.json').read_text())]


def test_encodings_preserve_all_facts_and_control_input(database):
    for case in cases():
        context = retrieve(ContextRequest(query=case.retrieval_query, context_size=case.context_size), database)
        graph, flat = (render(context, arm) for arm in ARMS)
        assert restore_tables(flat) == graph
        requests = [model_request(case, payload) for payload in (graph, flat)]
        assert requests[0]['options'] == requests[1]['options']
        assert requests[0]['format'] == requests[1]['format']
        assert requests[0]['messages'][0] == requests[1]['messages'][0]
        assert 'expected' not in requests[0]['messages'][1]['content']
        assert 'context' not in graph and 'context' not in flat


def test_interleaving_balances_first_arm_and_uses_fresh_independent_messages():
    plan = list(schedule(cases(), 5))
    assert len(plan) == 40
    first = [arm for _, _, arm in plan[::2]]
    assert first.count(ARMS[0]) == first.count(ARMS[1]) == 10
    for case in cases():
        starts = [arm for _, c, arm in plan[::2] if c.id == case.id]
        assert sorted(starts.count(arm) for arm in ARMS) == [2, 3]
        assert all(a != b for a, b in zip(starts, starts[1:]))
    for i in range(0, len(plan), 2):
        assert plan[i][:2] == plan[i + 1][:2]
        assert plan[i][2] != plan[i + 1][2]


def test_oracle_rejects_wrong_links_source_and_coverage(database):
    for case in cases():
        context = retrieve(ContextRequest(query=case.retrieval_query, context_size=case.context_size), database)
        answer = case.expected.model_dump()
        assert score(json.dumps(answer), case, context, True)['passed']
        assert not score(json.dumps(answer), case, context, False)['passed']
        wrong = {**answer, 'answer_ids': ['prod:invented']}
        assert score(json.dumps(wrong), case, context, True)['ungrounded_id']
        assert not score(json.dumps({**answer, 'source': 'none'}), case, context, True)['passed']
        assert not score(json.dumps({**answer, 'partial': not answer['partial']}), case, context, True)['passed']
        assert not score('not JSON', case, context, True)['passed']
        wrong_edge = {**answer, 'supporting_edges': [{'source':'prod:checkout','relation':'evaluates','target':'prod:commerce-team'}]}
        assert score(json.dumps(wrong_edge), case, context, True)['unsupported_relationship']
        if answer['supporting_edges']:
            assert not score(json.dumps({**answer, 'supporting_edges': []}), case, context, True)['relationship_ok']


def test_token_telemetry_must_be_actual_and_nonempty():
    response = {k: 1 for k in ('prompt_eval_count','eval_count','total_duration','load_duration','prompt_eval_duration','eval_duration')}
    response['done_reason'] = 'stop'
    assert measurements(response)['prompt_eval_cached_count'] is None
    with pytest.raises(SafeError):
        measurements({**response, 'prompt_eval_count': 0})
    with pytest.raises(SafeError):
        measurements({**response, 'eval_count': True})


@pytest.mark.asyncio
async def test_malformed_http_envelope_is_sanitized():
    import httpx
    from comparison.pilot import json_request
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=['private-value']))) as client:
        with pytest.raises(SafeError, match='^model_response_invalid$'):
            await json_request(client, 'GET', 'http://localhost/api/tags')


@pytest.mark.asyncio
async def test_prefetch_failure_keeps_sanitized_aborted_receipt(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import comparison.pilot as pilot
    class BrokenClient:
        def __init__(self, url): pass
        async def __aenter__(self):
            raise ValueError('private-value')
        async def __aexit__(self, *args): pass
    monkeypatch.setattr(pilot, 'Client', BrokenClient)
    path = tmp_path / 'receipt.json'
    with pytest.raises(SafeError, match='^mcp_prefetch_failed$'):
        await pilot.run(SimpleNamespace(output=str(path), repetitions=5, mcp_url='http://localhost/mcp'))
    record = json.loads(path.read_text())
    assert record['status'] == 'aborted' and not record['trials']
    assert 'private-value' not in path.read_text()


def test_summary_keeps_token_totals_and_incomplete_runs_distinct():
    from comparison.summarize import summarize
    rows = []
    for repetition in range(5):
        for arm, tokens in zip(ARMS, (100, 80), strict=True):
            rows.append({'request_identifier': str(len(rows)), 'case_id':'one', 'arm':arm, 'repetition':repetition, 'order':len(rows), 'error_category':'none', 'score':{'passed':True}, 'prompt_eval_count':tokens, 'eval_count':10, 'elapsed_seconds':1.0, 'request_sha256':arm})
    document = {'status':'completed','expected_trials':10,'case_count':1,'repetitions':5,'snapshots':[{'case_id':'one'}],'trials':rows}
    result = summarize(document)
    assert result['complete']
    assert result['flat_input_token_reduction_percent'] == 20
    assert result['totals']['graph_json']['input_tokens'] == 500
    assert result['totals']['flat_tables']['input_tokens'] == 400
    incomplete = summarize({**document, 'trials':rows[:-1]})
    assert not incomplete['complete'] and incomplete['flat_input_token_reduction_percent'] is None
