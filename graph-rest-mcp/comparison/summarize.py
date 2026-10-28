"""Aggregate sanitized study receipts without recovering raw answers."""
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median

from comparison.pilot import ARMS


def distribution(values):
    return {"median": median(values), "min": min(values), "max": max(values), "sum": sum(values)} if values else None


def summarize(document):
    rows = document['trials']
    complete = document['status'] == 'completed' and len(rows) == document['expected_trials']
    cases = [c['case_id'] for c in document['snapshots']]
    complete &= sorted(r['order'] for r in rows) == list(range(document['expected_trials']))
    complete &= len({r['request_identifier'] for r in rows}) == len(rows)
    groups = []
    for case in cases:
        for arm in ARMS:
            selected = [r for r in rows if r['case_id'] == case and r['arm'] == arm]
            complete &= len(selected) == document['repetitions'] and sorted(r['repetition'] for r in selected) == list(range(document['repetitions']))
            groups.append({'case_id': case, 'arm': arm, 'calls': len(selected), 'passes': sum(r.get('score', {}).get('passed', False) for r in selected), 'answer_matches': sum(r.get('score', {}).get('answer_ok', False) for r in selected), 'relationship_matches': sum(r.get('score', {}).get('relationship_ok', False) for r in selected), 'source_scope_matches': sum(r.get('score', {}).get('source_scope_ok', False) for r in selected), 'coverage_matches': sum(r.get('score', {}).get('coverage_ok', False) for r in selected), 'ungrounded_id_calls': sum(r.get('score', {}).get('ungrounded_id', False) for r in selected), 'unsupported_relationship_calls': sum(r.get('score', {}).get('unsupported_relationship', False) for r in selected), 'input_tokens': distribution([r['prompt_eval_count'] for r in selected if 'prompt_eval_count' in r]), 'output_tokens': distribution([r['eval_count'] for r in selected if 'eval_count' in r]), 'elapsed_seconds_diagnostic': distribution([r['elapsed_seconds'] for r in selected]), 'errors': dict(Counter(r['error_category'] for r in selected if r['error_category'] != 'none')), 'identical_request_across_repetitions': len({r['request_sha256'] for r in selected}) == 1})
    totals = {}
    for arm in ARMS:
        selected = [r for r in rows if r['arm'] == arm]
        totals[arm] = {'calls': len(selected), 'passes': sum(r.get('score', {}).get('passed', False) for r in selected), 'input_tokens': sum(r.get('prompt_eval_count', 0) for r in selected), 'output_tokens': sum(r.get('eval_count', 0) for r in selected), 'error_calls': sum(r['error_category'] != 'none' for r in selected), 'errors_by_category': dict(Counter(r['error_category'] for r in selected if r['error_category'] != 'none'))}
    inputs = [totals[a]['input_tokens'] for a in ARMS]
    return {'complete': complete, 'distinct_questions': document['case_count'], 'scored_calls': len(rows), 'groups': groups, 'totals': totals, 'flat_input_token_reduction_percent': round((inputs[0] - inputs[1]) / inputs[0] * 100, 2) if complete and inputs[0] else None, 'claim_boundary': 'four-question synthetic post-retrieval model-call pilot; production benefit inconclusive'}


def report(document, summary, receipt_name):
    totals = summary['totals']
    text = ['# Graph objects and flat tables on the same evidence', '', 'This is a four-question synthetic pilot at the model boundary. Both representations contain the same nodes, attributes, views and directed relationships retrieved through the working MCP server. It does not compare graph retrieval with missing relationship evidence.', '']
    if summary['complete']:
        reduction = summary['flat_input_token_reduction_percent']
        difference = f"{abs(reduction)}% {'fewer' if reduction >= 0 else 'more'}"
        text += [f"The study completed {summary['scored_calls']} scored calls, five repetitions per question and representation. Graph JSON passed {totals[ARMS[0]]['passes']}/{totals[ARMS[0]]['calls']} calls. Flat tables passed {totals[ARMS[1]]['passes']}/{totals[ARMS[1]]['calls']} calls.", '', f"Flat-table prompts used {difference} input tokens in this exact workload. Ollama reported {totals[ARMS[0]]['input_tokens']} graph input tokens and {totals[ARMS[1]]['input_tokens']} flat input tokens. These are post-retrieval model-call totals. They exclude Kagent orchestration, tool selection, gateway overhead and retrieval.", '']
    else:
        text += ['The run is incomplete. No comparative result is accepted.', '']
    text += ['| Question | Representation | Passes | Input tokens, median and range | Output tokens, median and range | Error calls |', '| --- | --- | --- | --- | --- | --- |']
    for g in summary['groups']:
        def display(value):
            return f"{value['median']} ({value['min']} to {value['max']})" if value else 'missing'
        text.append(f"| {g['case_id']} | {g['arm']} | {g['passes']}/{g['calls']} | {display(g['input_tokens'])} | {display(g['output_tokens'])} | {sum(g['errors'].values())} |")
    text += ['', '## What was held constant', '', f"Model `{document['model']}`, full digest `{document.get('model_digest', 'unavailable')}`, Ollama `{document.get('ollama_version', 'unavailable')}`. Both arms used the same instructions, questions, response schema and options `{json.dumps(document['options'], sort_keys=True)}`. Both received the same snapshot for each question. Table-to-graph equality and agreement with the frozen local fixture were checked before inference. Script, oracle, fixture, prompt and request hashes are recorded in [the receipts]({receipt_name}).", '', 'The two representations use graph object records or column-and-row tables. Their human-readable context summary was omitted from both arms. Metadata, limitations, source, scope and every relationship remain. The model received the evidence payload once. Reconstructed MCP JSON-RPC envelope sizes are separate byte measurements with synthetic ID zero and exclude HTTP/SSE framing.', '', 'The oracle requires the correct answer IDs, supporting directed edges for relationship answers, source/scope and partial coverage. It rejects IDs and edges unsupported by the returned context. The generic JSON output schema contains no expected answer IDs. Its supporting-edge objects use named source, relation and target fields, so flat rows must be converted into that object shape. This can favor graph-object input and limits generalization. The study scores observable evidence support, not hidden reasoning or unrestricted conversational quality. Zero unsupported-ID or unsupported-edge flags do not imply correctness. Choosing the wrong existing object or misstating partial coverage fails separate checks.', '', '## Repetition, errors and timing', '', 'Five paired repetitions were interleaved within each question, with question order rotated. Two unscored warm-ups preceded the run. Every scored request used a fresh one-turn message array. Temperature zero means repetitions check repeatability; these are four distinct questions, not forty independent questions. No scored request was automatically retried within a study, and no prompt or oracle was tuned after scored inference began.', '', f"Graph error categories: `{json.dumps(totals[ARMS[0]]['errors_by_category'], sort_keys=True)}`. Flat error categories: `{json.dumps(totals[ARMS[1]]['errors_by_category'], sort_keys=True)}`. An answer_mismatch is a scored wrong answer, not a transport failure. Raw answers, prompts and tool responses were not retained. Missing token telemetry aborts a run instead of estimating tokens.", '', 'Input/output counts come from Ollama prompt_eval_count and eval_count. Cache counts are recorded if available, otherwise null. CPU timings are diagnostic. Prefix caching, scheduler noise and shared host activity are not fully controlled, so no speed claim is made. The [startup observation](host-profile.json) records the four-core VM and the model pod’s three-CPU limit.', '', '## Memory recovery', '', 'The first attempt at the former 4 GiB model-container limit was OOM-killed after four completed scored calls. Its [aborted receipt](aborted-memory-limit-2026-10-27.json) retains two warm-ups, four completed scored calls and one interrupted call. Those calls contribute no comparative verdict. After checking VM headroom, only the model deployment memory changed to a 4 GiB request and 6 GiB limit. The full replacement study started from the beginning. Questions, prompt, oracle, model digest and inference options stayed unchanged. [Recovery record](memory-recovery.json).', '', '## Interpretation and limits', '', 'Flat tables repeat field names less often, so fewer input tokens can be an encoding effect. Both arms retain topology. This pilot cannot establish whether relationship evidence improves answers compared with entity-only data, whether Apache AGE retrieval is better, or whether a private remote endpoint is correct.', '', 'The fixture has few paths and only one policy per environment. Requiring supporting edges prevents a policy-ID guess alone from passing, but the dataset remains weak evidence for general multi-hop reasoning. Four synthetic questions on one small local model do not establish a hallucination-rate improvement or workplace productivity gain.', '', 'Production benefit remains inconclusive. Preserve the accepted bounded MCP integration and its explicit human-readable source and coverage warnings. Those prose cues were deliberately omitted from both arms here, so these quality counts do not describe the accepted native AgentTemplate workflow. Any recommendation to change workplace response encoding needs a broader independent question set and native Kagent input-token metering.', '', 'Read [the frozen plan](PLAN.md) and [reproduction instructions](README.md). Ollama counter definitions are documented at https://docs.ollama.com/api/chat.', '']
    return '\n'.join(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args()
    document = json.loads(args.receipt.read_text())
    summary = summarize(document)
    (args.summary or args.receipt.with_suffix('.summary.json')).write_text(json.dumps(summary, indent=2) + '\n')
    (args.report or args.receipt.with_suffix('.md')).write_text(report(document, summary, args.receipt.name))
    print(json.dumps({'complete': summary['complete'], 'totals': summary['totals'], 'flat_input_token_reduction_percent': summary['flat_input_token_reduction_percent']}))


if __name__ == '__main__':
    main()
