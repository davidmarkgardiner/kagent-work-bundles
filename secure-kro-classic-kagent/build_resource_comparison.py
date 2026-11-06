"""Build an offline before/after resource sheet from the checked bundle sources."""
import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path

import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
bundle = args.bundle.resolve()
output = args.output or bundle / 'resources.html'
notes = json.loads((bundle / 'demo/resource-notes.json').read_text())
graph = yaml.safe_load((bundle / 'demo/yaml/catalog/resourcegraphdefinition.yaml').read_text())
nodes = graph['spec']['resources']
assert len(nodes) == 14 and {n['id'] for n in nodes} == set(notes)
counts = Counter(n['template']['kind'] for n in nodes)
initial_agent = {
    'apiVersion': 'kagent.dev/v1alpha2', 'kind': 'Agent',
    'metadata': {'name': 'demo', 'namespace': 'classic-agents'},
    'spec': {
        'type': 'Declarative',
        'declarative': {
            'runtime': 'go', 'modelConfig': 'approved-model',
            'systemMessage': 'Read approved Kubernetes information. Return bounded evidence. Do not change resources.',
            'tools': [{'type': 'McpServer', 'mcpServer': {
                'apiGroup': 'kagent.dev', 'kind': 'RemoteMCPServer',
                'name': 'approved-kubernetes-mcp',
                'toolNames': ['k8s_get_resources', 'k8s_get_events']}}]},
        'skills': {'gitRefs': [{'url': '{{APPROVED_GITLAB_SKILLS_REPOSITORY_URL}}',
                              'ref': '{{APPROVED_FULL_COMMIT_ID}}',
                              'path': 'skills/work-guidance', 'name': 'work-guidance'}],
                   'gitAuthSecretRef': {'name': 'approved-git-credentials'}}}}
initial_deployment = {
    'apiVersion': 'apps/v1', 'kind': 'Deployment',
    'metadata': {'name': 'demo', 'namespace': 'classic-agents'},
    'spec': {'replicas': 1,
             'selector': {'matchLabels': {'app': 'kagent', 'kagent': 'demo'}},
             'template': {'metadata': {'labels': {'app': 'kagent', 'kagent': 'demo'}},
                          'spec': {'containers': [{'name': 'agent',
                              'image': '{{APPROVED_NATIVE_KAGENT_RUNTIME_IMAGE}}',
                              'args': ['--host', '0.0.0.0', '--port', '8080', '--filepath', '/config'],
                              'ports': [{'containerPort': 8080}],
                              'volumeMounts': [{'name': 'config', 'mountPath': '/config'}]}],
                              'volumes': [{'name': 'config', 'secret': {'secretName': 'demo'}}]}}}}
initial = [
    {'id': 'agent', 'title': 'Agent', 'kind': 'Agent', 'group': 'Agent definition', 'owner': 'Team supplies; kagent reconciles',
     'purpose': 'The system prompt, approved model, selected skill, and named MCP tools define the useful agent.',
     'change': 'The initial example has no composed Gateway JWT front door or dedicated ingress NetworkPolicy. Tool permissions still come from the MCP adapter and backend.',
     'origin': 'Illustrative native Agent, derived from the catalog bindings. Not a historical live snapshot.',
     'path': 'demo/yaml/catalog/04-agent.yaml',
     'yaml': '# Initial comparison example only. Not a historical deployment receipt.\n' + yaml.safe_dump(initial_agent, sort_keys=False)},
    {'id': 'deployment', 'title': 'Deployment', 'kind': 'Deployment', 'group': 'kagent runtime output', 'owner': 'kagent controller',
     'purpose': 'Runs the agent API process. kagent generates the runtime Deployment from the Agent.',
     'change': 'The composition in the next tab adds a dedicated runtime identity, restricted pod settings, and network intent around this same native runtime.',
     'origin': 'Illustrative, abbreviated controller-output shape. The controller also generates its configuration Secret; no Secret contents are shown.',
     'path': 'demo/recorded-native-deployment.yaml',
     'yaml': '# Illustrative runtime shape, abbreviated for comparison. Not an apply file.\n' + yaml.safe_dump(initial_deployment, sort_keys=False)},
    {'id': 'service', 'title': 'Service', 'kind': 'Service', 'group': 'kagent runtime output', 'owner': 'kagent controller',
     'purpose': 'Gives the runtime a cluster-internal API address on port 8080.',
     'change': 'In this initial comparison, a workload with network reachability can invoke that API without the Gateway JWT controls added in the secure tab.',
     'origin': 'Existing illustrative Service shape. ClusterIP is routing, not caller authentication.',
     'path': 'demo/yaml/nativeService.yaml'},
    {'id': 'model', 'title': 'ModelConfig', 'kind': 'ModelConfig', 'group': 'Existing platform references', 'owner': 'Platform',
     'purpose': 'Connects the Agent to the approved model endpoint and an existing credential reference.',
     'change': 'Reused by the secure agent. The team selects its name; a provider key is not placed in the customer request.',
     'origin': 'Existing sanitized reference example, not an installed-model inventory.', 'path': 'demo/yaml/model.yaml'},
    {'id': 'mcp', 'title': 'RemoteMCPServer', 'kind': 'RemoteMCPServer', 'group': 'Existing platform references', 'owner': 'Platform',
     'purpose': 'Names the approved Kubernetes MCP endpoint. The Agent exposes only its selected read-only tool names.',
     'change': 'Reused by the secure agent. Model access, tool access, and backend resource permission remain separate.',
     'origin': 'Existing sanitized MCP reference. Real endpoint discovery and permission tests remain separate.', 'path': 'demo/yaml/remoteMCP.yaml'}]
secure = []
for node in nodes:
    ident = node['id']
    source = next((bundle / 'demo/yaml/catalog').glob('*-' + ident + '.yaml'))
    secure.append({'id': ident, 'title': notes[ident]['title'], 'kind': node['template']['kind'],
                   'group': 'KRO creates per agent · 14 resources', 'owner': 'KRO',
                   'purpose': notes[ident]['explanation'],
                   'change': 'This native Agent is now assembled with the prescribed security configuration.' if ident == 'agent' else 'Added by the secure KRO composition. The customer does not author or manage this child resource directly.',
                   'origin': 'Exact catalog-profile RGD resource template. KRO resolves the ${...} CEL references. No deployment runs here.',
                   'path': str(source.relative_to(bundle))})
shared = [
    ('graph', 'ResourceGraphDefinition', 'ResourceGraphDefinition', 'demo/yaml/catalog/resourcegraphdefinition.yaml',
     'Defines the customer schema and the 14-resource dependency graph. The caller route depends on Golden Job success.'),
    ('gateway', 'Gateway', 'Gateway', 'demo/yaml/platform-classic-demo.yaml',
     'Provides separate caller and verifier listeners. allowedRoutes controls which namespaces may attach HTTPRoutes; it does not authenticate callers.'),
    ('callerListener', 'Caller listener policy', 'AgentgatewayPolicy', 'demo/yaml/platform-classic-listener-caller.yaml',
     'Protects the shared caller listener with strict JWT validation and the exact caller identity before customer routes are added.'),
    ('verifierListener', 'Verifier listener policy', 'AgentgatewayPolicy', 'demo/yaml/platform-classic-listener-verify.yaml',
     'Keeps verification traffic on its own listener and verifier identity. It is installed before an agent instance.'),
    ('model', 'Approved ModelConfig', 'ModelConfig', 'demo/yaml/model.yaml',
     'Reuses the approved native model connection and platform-owned credential reference.'),
    ('mcp', 'Approved RemoteMCPServer', 'RemoteMCPServer', 'demo/yaml/remoteMCP.yaml',
     'Reuses the approved MCP endpoint. Selected tool names and the adapter backend permissions still constrain real operations.')]
for ident, title, kind, path, purpose in shared:
    secure.append({'id': ident, 'title': title, 'kind': kind, 'path': path,
                   'group': 'Platform provides beforehand · outside the 14', 'owner': 'Platform',
                   'purpose': purpose, 'change': 'Shared or reused configuration, not another per-agent KRO child.',
                   'origin': 'Exact checked graph/baseline or clearly marked reference example. Environment-specific values stay as placeholders.'})
for ident, title, kind, path, origin in [
    ('deployment', 'Native runtime Deployment', 'Deployment', 'demo/recorded-native-deployment.yaml', 'Sanitized controller output recorded on 4 November 2026. Not current live state or an initial-deployment snapshot.'),
    ('service', 'Native runtime Service', 'Service', 'demo/yaml/nativeService.yaml', 'Illustrative controller-owned Service shape, not a live Service snapshot.')]:
    secure.append({'id': ident, 'title': title, 'kind': kind, 'path': path,
                   'group': 'kagent generates · outside the 14', 'owner': 'kagent controller',
                   'purpose': 'kagent generates the runtime Deployment, Service, and configuration Secret from the native Agent. Secret contents are deliberately omitted.',
                   'change': 'KRO owns the Agent definition. kagent owns this generated runtime object.', 'origin': origin})
secure.append({'id': 'referenceGrant', 'title': 'Conditional ReferenceGrant', 'kind': 'ReferenceGrant',
               'path': 'demo/yaml/referenceGrant.yaml', 'group': 'Optional pattern · not installed here', 'owner': 'Backend namespace owner',
               'purpose': 'Permits a specified cross-namespace HTTPRoute-to-Service reference. The checked same-namespace layout needs no ReferenceGrant.',
               'change': 'Use only for a reviewed cross-namespace variant. A grant does not authenticate a caller or grant network/API permission.',
               'origin': 'Existing conditional reference example. Not installed by this graph and not counted among the 14.'})

css = '''
:root{--ink:#191919;--paper:#f4f3ee;--red:#e60000;--line:#d7d5ce;--blue:#245a8b;--muted:#575752}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}a{color:var(--blue);text-underline-offset:4px}header{padding:17px 4vw;border-bottom:1px solid var(--line);display:flex;gap:24px;align-items:center}header strong{color:var(--red);font-size:24px;letter-spacing:-1px}header nav{display:flex;gap:20px;font-size:13px;flex-wrap:wrap}main{max-width:1500px;margin:auto;padding:22px 32px 35px}.eyebrow{font-weight:750;font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);margin:0 0 12px}.eyebrow:before{content:"";display:inline-block;width:32px;height:4px;background:var(--red);margin-right:12px}h1{font-size:40px;line-height:1.1;letter-spacing:-.04em;margin:0 0 16px}h2{font-size:29px;line-height:1.15;letter-spacing:-.03em;margin:0 0 13px}h3{font-size:21px;line-height:1.2;margin:0 0 10px}p{margin:0 0 14px}.lead{font-size:20px;color:#3e3e39;max-width:1100px}.modes{border:0;padding:0;margin:20px 0 0;display:grid;grid-template-columns:1fr 1fr;gap:0;min-width:0}.sr,.choice{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.mode-label{padding:17px 24px;background:#e5e4df;border:1px solid var(--line);font-size:19px;font-weight:700;cursor:pointer}.mode-panel{display:none;grid-column:1/-1;background:white;border:1px solid var(--line);border-top:0;padding:24px;min-width:0}#initial:checked~label[for=initial],#secure:checked~label[for=secure]{background:var(--ink);border-color:var(--ink);color:white;box-shadow:inset 0 -4px var(--red)}#initial:checked~#initial-panel,#secure:checked~#secure-panel{display:block}.choice:focus-visible~label.mode-label{outline-offset:-5px}#initial:focus-visible~label[for=initial],#secure:focus-visible~label[for=secure]{outline:3px solid var(--blue)}.flow{display:flex;align-items:stretch;margin:17px 0}.step{flex:1;min-width:0;border:1px solid var(--line);background:var(--paper);padding:15px;font-size:14px}.step b{display:block;font-size:17px;margin-bottom:5px}.arrow{align-self:center;padding:0 9px;color:var(--red);font-weight:800}.boundary{border-left:4px solid var(--red);padding:12px 17px;background:var(--paper);font-size:15px;margin:20px 0}.counts{display:flex;gap:8px;flex-wrap:wrap;margin:17px 0}.counts span{font-size:12px;border:1px solid var(--line);padding:5px 9px;background:#fafaf7}.resources{position:relative;display:grid;grid-template-columns:285px minmax(0,1fr);gap:24px;margin-top:23px;align-items:start;min-width:0}.resource-nav{max-height:690px;overflow-y:auto;border:1px solid var(--line);background:#fafaf7}.group{padding:15px 14px 6px;color:var(--muted);font-size:11px;letter-spacing:.05em;text-transform:uppercase;font-weight:750;margin:0}.resource-label{display:block;cursor:pointer;margin:4px 7px;padding:10px 12px;border:1px solid transparent;border-radius:4px;font-size:14px;line-height:1.3}.resource-label small{display:block;color:var(--muted);font-size:11px;margin-top:4px}.resource-label:hover{border-color:var(--line);background:white}.resource-panel{display:none;min-width:0}.tag{display:inline-block;border:1px solid var(--blue);color:var(--blue);padding:4px 7px;font-size:11px;margin-bottom:12px}.change{border-left:3px solid var(--red);padding:8px 13px;background:var(--paper);font-size:14px}.origin{font-size:12px;color:var(--muted);margin:14px 0 7px}.source{font:12px/1.5 ui-monospace,Consolas,monospace;overflow-wrap:anywhere}pre{background:#f4f3ee;border:1px solid var(--line);padding:20px;font:13px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;overflow:auto;max-height:430px;margin:12px 0 0;tab-size:2}pre:focus-visible,a:focus-visible{outline:3px solid var(--blue);outline-offset:3px}.footer{border-top:1px solid var(--line);margin:25px 0 0;padding-top:15px;font-size:12px;color:var(--muted)}.print-note{display:none}
.resource-panel{grid-template-columns:minmax(200px,.7fr) minmax(0,1.3fr);gap:20px}.resource-panel pre{margin-top:0;max-height:500px}.resource-nav{max-height:500px}
@media(max-width:800px){.resource-panel{grid-template-columns:1fr}header{display:block;padding:14px 17px}header nav{margin-top:9px;gap:13px}main{padding:23px 12px}h1{font-size:35px}.lead{font-size:18px}.mode-label{padding:13px;font-size:16px}.mode-panel{padding:23px 18px}.flow{flex-direction:column}.arrow{transform:rotate(90deg);padding:4px}.resources{grid-template-columns:1fr;gap:20px}.resource-nav{max-height:230px}.resource-label{padding:9px 11px}pre{font-size:12px;max-height:430px}.counts{gap:5px}}
@media print{header,.mode-label,.resource-nav,.counts,.screen-note{display:none}body{background:white}main{padding:0;max-width:none}h1{font-size:30px}.lead{font-size:15px}.modes{display:block;margin-top:15px}.mode-panel{display:block!important;border:0;padding:15px 0;break-before:page}.flow{flex-direction:row}.arrow{transform:none;padding:0 6px}.step{font-size:11px;padding:10px}.step b{font-size:14px}.resources{display:block;margin-top:15px}.resource-panel{display:none!important}#initial-agent-panel,#secure-golden-panel{display:block!important}pre{font-size:10px;max-height:none;overflow:visible;white-space:pre-wrap}.print-note{display:block;font-size:12px}.boundary{font-size:12px}.origin,.source{font-size:10px}.footer{font-size:10px}h2{font-size:25px}}
'''
panels = []
mode_data = [
    ('initial', 'Initial deployment', initial, 'agent',
     'The agent already has useful capabilities.',
     'A native kagent Agent connects its system prompt, approved model, selected skill, and MCP tools. kagent runs it behind a cluster-internal Service.',
     [('Cluster workload', 'A caller with network reachability.'), ('Service API', 'The native A2A endpoint on port 8080.'), ('Agent runtime', 'Prompt + skills + selected MCP tools.'), ('Approved backends', 'The model endpoint and read-only MCP.')],
     'In this illustrated starting point, callers that can reach the Service can invoke the API. There is no composed Gateway JWT protection or dedicated ingress policy. A native kagent installation can also be secured separately.'),
    ('secure', 'Secure agent with KRO', secure, 'golden',
     'KRO adds the repeatable security composition.',
     'The useful native agent remains. KRO now assembles its identities, network intent, JWT policies, protected routes, and Golden verification.',
     [('Caller JWT', 'Expected issuer, audience, and caller subject.'), ('Agent Gateway', 'Shared listeners + JWT authorization.'), ('Protected HTTPRoute', 'Caller route appears after Golden succeeds.'), ('Native Agent', 'Same runtime and approved backends.')],
     'KRO creates 14 per-agent resources. Golden succeeds before the caller HTTPRoute is created. These are dependency groups, not a claim that every object is deployed serially. This page runs no Job, request, or cluster operation.')]
for mode, title, entries, default, heading, intro, steps, boundary in mode_data:
    radios = []
    labels = []
    views = []
    last_group = None
    for entry in entries:
        ident = mode + '-' + entry['id']
        radio = ident + '-choice'
        radios.append(f'<input class="choice" type="radio" name="{mode}-resource" id="{radio}" aria-controls="{ident}-panel"' + (' checked' if entry['id'] == default else '') + '>')
        if entry['group'] != last_group:
            labels.append('<p class="group">' + escape(entry['group']) + '</p>')
            last_group = entry['group']
        labels.append(f'<label class="resource-label" for="{radio}">{escape(entry["title"])}<small>{escape(entry["kind"])}</small></label>')
        text = entry.get('yaml') or (bundle / entry['path']).read_text()
        views.append(f'<article class="resource-panel" id="{ident}-panel" aria-labelledby="{ident}-heading"><div class="resource-info"><span class="tag">{escape(entry["owner"])}</span><h3 id="{ident}-heading">{escape(entry["title"])}</h3><p>{escape(entry["purpose"])}</p><p class="change">{escape(entry["change"])}</p><p class="origin">{escape(entry["origin"])}</p><p class="source">Source · {escape(entry["path"])}</p></div><pre tabindex="0" aria-label="{escape(entry["title"])} YAML">{escape(text)}</pre></article>')
        css += f'#{radio}:checked~#{ident}-panel{{display:grid}}#{radio}:checked~.resource-nav label[for="{radio}"]{{background:#191919;color:white;border-color:#191919}}#{radio}:checked~.resource-nav label[for="{radio}"] small{{color:#deded9}}#{radio}:focus-visible~.resource-nav label[for="{radio}"]{{outline:3px solid #245a8b;outline-offset:1px}}\n'
    flow = '<div class="flow" aria-label="' + escape(title) + ' request path">' + '<span class="arrow" aria-hidden="true">→</span>'.join('<div class="step"><b>' + escape(a) + '</b>' + escape(b) + '</div>' for a, b in steps) + '</div>'
    chips = ''
    if mode == 'secure':
        chips = '<div class="counts" aria-label="The 14 KRO-created resources">' + ''.join('<span>' + str(counts[kind]) + ' ' + escape(kind) + '</span>' for kind in ['ServiceAccount', 'Agent', 'NetworkPolicy', 'AgentgatewayPolicy', 'HTTPRoute', 'ConfigMap', 'Job']) + '</div>'
    panels.append(f'<section class="mode-panel" id="{mode}-panel" aria-labelledby="{mode}-heading"><h2 id="{mode}-heading">{escape(heading)}</h2><p>{escape(intro)}</p>{flow}<p class="boundary">{escape(boundary)}</p>{chips}<p class="screen-note">Choose a resource to see its purpose, owner, and YAML. Use the arrow keys when a resource selector has keyboard focus. YAML is selectable text.</p><p class="print-note">The printed view shows one representative YAML resource per mode. Open this HTML to inspect every resource.</p><div class="resources" role="group" aria-label="{escape(title)} resource selector">' + ''.join(radios) + '<aside class="resource-nav" aria-label="Resource choices">' + ''.join(labels) + '</aside>' + ''.join(views) + '</div></section>')

summary_rows = [
    ('Agent', 'The agent definition', 'Connects the system prompt, model, skills, and selected MCP tools.'),
    ('ServiceAccount', 'Runtime, verifier, caller', 'Gives the agent, its test, and its caller separate identities.'),
    ('NetworkPolicy', 'Agent and verifier boundaries', 'Restricts which network paths each workload may use.'),
    ('AgentgatewayPolicy', 'Verification, card, caller checks', 'Validates JWTs and authorizes the intended identity on each route.'),
    ('HTTPRoute', 'AgentCard, verification, invocation', 'Sends each request to the correct agent endpoint.'),
    ('ConfigMap', 'Golden test configuration', 'Fixes the expected agent, endpoints, and verification settings.'),
    ('Job', 'Golden verification', 'Checks the agent before KRO creates the caller route.'),
]
assert set(counts) == {row[0] for row in summary_rows}
rows_html = ''.join('<tr><th scope="row"><code>' + escape(kind) + '</code><span class="kind-count">' + str(counts[kind]) + '</span></th><td>' + escape(instances) + '</td><td>' + escape(reason) + '</td></tr>' for kind, instances, reason in summary_rows)
hardening = [
    ('Check the caller', 'Require the expected JWT issuer, audience, expiry, and exact caller identity.'),
    ('Separate identities', 'Keep runtime, verifier, and caller distinct. Golden has no Kubernetes API Role or RoleBinding.'),
    ('Restrict network paths', 'Allow approved Gateway ingress and bounded egress. Enforcement needs the receiving cluster\'s CNI.'),
    ('Restrict the process', 'Use non-root, no privilege escalation, read-only root, dropped capabilities, and seccomp. Bound temporary storage, CPU, and memory.'),
    ('Limit capabilities', 'Select approved models and explicit MCP tool names. Backend permissions remain a separate check.'),
    ('Verify before exposure', 'Create the caller route only after Golden succeeds. A past pass is not continuous revocation.'),
]
cards_html = ''.join('<article class="hardening-card"><span class="card-number">' + str(i) + '</span><h3>' + escape(title) + '</h3><p>' + escape(text) + '</p></article>' for i, (title, text) in enumerate(hardening, 1))
css += '''
html{scroll-padding-top:20px}.summary-sheet{background:white;border:1px solid var(--line);padding:34px 38px;margin:0 0 24px;scroll-margin-top:18px}.summary-sheet h1{font-size:39px}.summary-sheet h2{font-size:36px}.summary-sheet .lead{font-size:19px;margin-bottom:19px}.inventory-table{width:100%;border-collapse:collapse;font-size:15px;margin:18px 0 19px}.inventory-table th,.inventory-table td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:12px 13px}.inventory-table thead th{background:var(--paper);font-size:12px;color:var(--muted);letter-spacing:.04em;text-transform:uppercase}.inventory-table tbody th{width:25%;font-weight:650}.inventory-table td:nth-child(2){width:29%}.inventory-table code{font:14px/1.5 ui-monospace,Consolas,monospace;overflow-wrap:anywhere}.kind-count{display:inline-block;margin-left:10px;color:var(--red);font-weight:800}.ownership{display:grid;grid-template-columns:.75fr 1.5fr 1fr;gap:13px}.ownership p{margin:0;background:var(--paper);border:1px solid var(--line);padding:13px;font-size:12px}.ownership strong{display:block;font-size:14px;margin-bottom:5px}.simple-note{font-size:12px;color:var(--muted);margin:15px 0 0}.hardening-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px;margin:17px 0}.hardening-card{border:1px solid var(--line);background:#fafaf7;padding:17px;min-width:0}.hardening-card h3{font-size:17px;margin-bottom:8px}.hardening-card p{font-size:14px;margin:0}.card-number{display:block;color:var(--red);font-weight:800;font-size:12px;margin-bottom:7px}.simple-flow{display:flex;gap:11px;align-items:center;margin:18px 0}.simple-flow div{flex:1;min-width:0;background:var(--paper);border:1px solid var(--line);padding:14px 17px;font-size:15px}.simple-flow div strong{display:block;font-size:16px;margin-bottom:4px}.simple-flow span{color:var(--red);font-weight:800}.route-reasons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px;padding-top:14px;border-top:1px solid var(--line)}.route-reasons p{font-size:13px;margin:0}.route-reasons strong{display:block;font-size:14px;margin-bottom:4px}.technical-details{border:1px solid var(--line);padding:18px 22px;background:white}.technical-details>summary{cursor:pointer;color:var(--blue);font-size:16px;font-weight:700}.technical-intro{font-size:14px;color:var(--muted);margin:15px 0}.secondary-links{font-size:13px;margin:20px 0 0}.secondary-links a{margin-right:15px}a,summary{overflow-wrap:anywhere}summary:focus-visible{outline:3px solid var(--blue);outline-offset:5px}
@media(max-width:800px){header nav{gap:14px}.summary-sheet{padding:25px 19px}.summary-sheet h1,.summary-sheet h2{font-size:31px}.summary-sheet .lead{font-size:17px}.inventory-table{font-size:13px}.inventory-table th,.inventory-table td{padding:11px 7px}.inventory-table code{font-size:12px}.inventory-table tbody th{width:30%}.inventory-table td:nth-child(2){width:27%}.kind-count{display:block;margin:3px 0 0}.ownership,.hardening-grid,.route-reasons{grid-template-columns:1fr}.simple-flow{flex-direction:column;align-items:stretch}.simple-flow span{align-self:center;transform:rotate(90deg)}.technical-details{padding:18px 12px}}
@page{size:A3 landscape;margin:12mm}
@media print{header,.technical-details,.secondary-links{display:none!important}body{font-size:13px}main{padding:0;max-width:none}.summary-sheet{border:0;padding:9mm 11mm;margin:0;min-height:245mm;break-after:page;break-inside:avoid}.summary-sheet:nth-of-type(2){break-after:auto}.summary-sheet h1,.summary-sheet h2{font-size:34px}.summary-sheet .lead{font-size:17px}.inventory-table{font-size:13px}.inventory-table th,.inventory-table td{padding:10px 12px}.inventory-table code{font-size:13px}.kind-count{display:inline-block;margin-left:10px}.ownership{grid-template-columns:.75fr 1.5fr 1fr}.ownership p{font-size:11px}.hardening-grid,.route-reasons{grid-template-columns:repeat(3,minmax(0,1fr))}.hardening-card{padding:15px}.hardening-card p{font-size:13px}.simple-flow{flex-direction:row;align-items:center}.simple-flow span{transform:none}.simple-note{font-size:11px}.summary-sheet,.ownership p,.hardening-card,.simple-flow div{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
'''
main_sheets = '''<section class="summary-sheet" id="inventory" aria-labelledby="inventory-heading"><p class="eyebrow">Story 1 · 01 / 02</p><h1 id="inventory-heading">What gets deployed, and why?</h1><p class="lead">KRO uses a ResourceGraphDefinition to reconcile these 14 per-agent resources. Native kagent runs the agent.</p><table class="inventory-table"><thead><tr><th scope="col">Resource kind / count</th><th scope="col">Which instances?</th><th scope="col">Why deploy it?</th></tr></thead><tbody>''' + rows_html + '''</tbody></table><div class="ownership" aria-label="Outside the 14 per-agent resources"><p><strong>The team submits</strong>One ClassicSecureAgent request.</p><p><strong>The platform provides</strong>ResourceGraphDefinition, Namespace, Gateway, and two listener policies. Reused: GatewayClass, ModelConfig, RemoteMCPServer, and credentials.</p><p><strong>kagent generates</strong>Deployment, then ReplicaSet/Pods; Service; configuration Secret.</p></div><p class="simple-note">Those supporting objects are outside the 14. A ReferenceGrant is needed only for a cross-namespace backend reference; this same-namespace demo does not install one.</p></section>
<section class="summary-sheet" id="hardening" aria-labelledby="hardening-heading"><p class="eyebrow">Story 1 · 02 / 02</p><h2 id="hardening-heading">How the agent is hardened</h2><p class="lead">Routes choose the destination. Policies decide who may use it. Workload controls constrain execution.</p><div class="simple-flow" aria-label="Protected request path"><div><strong>Caller JWT</strong>Identity for this API.</div><span aria-hidden="true">→</span><div><strong>HTTPRoute + JWT policy</strong>Route and authorize.</div><span aria-hidden="true">→</span><div><strong>Agent Service</strong>Reach the native runtime.</div></div><div class="hardening-grid">''' + cards_html + '''</div><div class="route-reasons" aria-label="Why there are three HTTPRoutes"><p><strong>AgentCard route</strong>Lets the verifier discover the agent interface.</p><p><strong>Verification route</strong>Lets Golden test the agent separately from callers.</p><p><strong>Caller route</strong>The approved invocation endpoint, created after Golden passes.</p></div><p class="simple-note">4 November proof covers model/caller PONG and JWT denials. Network enforcement, MCP access, and telemetry need separate proof. These sheets explain templates, not a new deployment.</p></section>'''
inspector = '''<details class="technical-details" id="yaml-details"><summary>Optional resource-by-resource YAML</summary><p class="technical-intro">Compare the initial and secure definitions, then inspect each resource. These controls change the view only.</p><fieldset class="modes"><legend class="sr">Deployment comparison</legend><input class="choice" type="radio" name="deployment-mode" id="initial" aria-controls="initial-panel" checked><label class="mode-label" for="initial">1. Initial deployment</label><input class="choice" type="radio" name="deployment-mode" id="secure" aria-controls="secure-panel"><label class="mode-label" for="secure">2. Secure agent with KRO</label>''' + ''.join(panels) + '''</fieldset></details>'''
document = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'"><link rel="icon" href="data:,"><title>DICE | What we deploy and how we harden it</title><style>''' + css + '''</style></head><body><header><strong>DICE</strong><nav aria-label="Two-sheet walkthrough"><a href="#inventory">1. What gets deployed</a><a href="#hardening">2. How it is hardened</a><a href="showcase.html">Review sheets</a></nav></header><main>''' + main_sheets + inspector + '''<p class="secondary-links"><a href="tomorrow.html">Desired state and Entra</a><a href="presentation.html">Full YAML explorer</a></p></main></body></html>'''
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(document)
print(f'Built {output}: two summary sheets, {len(nodes)} KRO resources, and {len(initial) + len(secure)} optional YAML views.')
