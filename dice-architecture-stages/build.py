from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent
INK, MUTED, PAPER, LINE = '#1C1C1C', '#555952', '#F4F3EE', '#CCCABC'
RED, BLUE, GREEN = '#C72127', '#245F86', '#28634B'
STAGES = [
    dict(n=1, key='jwt', file='01-jwt.svg', title='Start with JWT authentication',
         delta='Protect the agent API and its tool routes.',
         intro='The client presents a signed JWT. The receiving gateway validates it and authorizes the requested agent or operation. The agent uses separate credentials for tool and model calls.',
         points=[('Caller authentication', 'A trusted issuer signs a token for the agent API. The gateway checks its signature, issuer, audience and validity period before applying caller permissions.'),
                 ('Credential handling', 'This baseline illustrates manually provisioned bearer credentials in Kubernetes Secrets. JWT itself does not require this storage pattern. The platform owner manages expiry, replacement and access.'),
                 ('Service flow', 'The gateway routes an accepted invocation to the agent. Tool and model calls return through approved gateway routes. Each destination has its own authentication contract.')],
         talk='First show a protected request. A valid token establishes identity, and policy decides which agent or operation that identity may use. Keep credentials out of instructions and tool results.'),
    dict(n=2, key='entra', file='02-entra-workload-identity.svg', title='Add Microsoft Entra workload identity',
         delta='Replace stored credentials with a federated token exchange.',
         intro='Keep JWT validation at the API. Change how the calling workloads obtain credentials. AKS projects a short-lived service-account assertion, and a trusted credential adapter exchanges it with Entra for a destination access token.',
         points=[('The handshake', 'Entra checks a federated identity credential that binds the AKS OIDC issuer, the service-account subject and the assertion audience to a user-assigned managed identity, or UAMI.'),
                 ('What leaves the Secret', 'The illustrated federated path needs no stored client secret, private signing key or provisioned bearer token in a Kubernetes Secret. Public identity references and trust configuration remain in reviewed configuration.'),
                 ('What remains sensitive', 'The projected assertion and the returned access token remain short-lived credentials. Keep their mounts and adapter operations unreachable by model-controlled shell or code tools. Same-pod token-file access defeats that isolation.'),
                 ('Separate identities and permissions', 'Give the caller, agent and MCP backend separate service accounts, identities and grants. The API enforces required application roles or an explicit caller ACL. A token with the right audience alone is insufficient. Entra Agent ID or delegated user access needs a separately reviewed flow.')],
         talk='The API still receives a JWT. We remove manual credential distribution for this connection. A workload proves its Kubernetes identity, Entra recognizes the configured trust, and the adapter obtains a token for the exact API.'),
    dict(n=3, key='observability', file='03-observability.svg', title='Add correlated observability',
         delta='Follow a request across the gateway, agent and MCP service.',
         intro='Keep the identity and request paths from view 2. Add OpenTelemetry instrumentation and an approved Alloy or OTel collection path into Loki, Grafana, Tempo and Mimir.',
         points=[('Follow one request', 'Propagate trace context across supported hops. Record gateway decisions, agent spans, MCP operations, errors and latency. Label every record with the relevant release and operation identifiers.'),
                 ('Collect approved metadata', 'Drop authorization headers, tokens and credentials before export. Prompt and result content require explicit data-handling approval and redaction. Instrumentation coverage must be verified per component.'),
                 ('Explain usage', 'Record model-provider usage where reported, with the source and model route. Missing usage stays unknown. Cost requires a versioned price basis and is an estimate until reconciled with billing.')],
         talk='Now follow the same request through its trace. Logs and metrics explain what happened and where it failed. Those signals do not by themselves tell us whether the answer was correct.'),
    dict(n=4, key='evaluation', file='04-evaluation.svg', title='Add release and runtime evaluation',
         delta='Judge behavior against explicit cases and keep reviewable receipts.',
         intro='Keep the observability layer. Add a release evaluation path and runtime assessments under approved data, identity and spend limits. Bind every verdict to the exact agent, skill, tool, policy and model versions.',
         points=[('Before a release', 'Run functional, tool-selection, security and quality cases against the candidate. A receipt binds the cases, evaluator, rubric and thresholds to that candidate. Existing review and approval determine promotion.'),
                 ('After a release', 'Use approved samples or replay cases with known expectations and context. Runtime assessment combines permitted evidence with the evaluation rubric. A trace without an expected outcome is insufficient for a correctness score.'),
                 ('Keep the decision inspectable', 'Store PASS, FAIL or UNKNOWN with evidence references, hard policy failures and version information. Missing evidence stays UNKNOWN. Findings feed operations and the next reviewed revision, without granting deployment authority.')],
         talk='Finally ask whether the agent did the right thing. Evaluate a known version against known cases, keep the receipt, and use the result in the existing release review. Runtime findings feed the next change.')
]


def text(x, y, value, size=23, color=INK, weight=400, anchor='start', extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{escape(value)}</text>'


def box(x, y, w, h, title, lines, accent=LINE, tint='white'):
    out = [f'<g class="node"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{tint}" stroke="{LINE}" stroke-width="2"/>',
           f'<path d="M{x} {y}H{x+w}" stroke="{accent}" stroke-width="5"/>', text(x+22, y+43, title, 29, weight=600)]
    out.extend(text(x+22, y+82+i*30, line) for i, line in enumerate(lines))
    return ''.join(out)+'</g>'


def edge(d, color=INK, dashed=False, arrow=True):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3" '+('stroke-dasharray="9 7" ' if dashed else '')+(f'marker-end="url(#arrow)"' if arrow else '')+'/>'


def label(x, y, value, color=MUTED, anchor='middle', size=21):
    return text(x, y, value, size, color, anchor=anchor,
                extra=f'paint-order="stroke" stroke="{PAPER}" stroke-width="8" stroke-linejoin="round"')


def shell(title, desc, h, contents):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 {h}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="context-stroke"/></marker></defs>
<style>text{{font-family:Arial,Helvetica,sans-serif}}</style><rect width="100%" height="100%" fill="{PAPER}"/>
{contents}</svg>'''


def overview(stage):
    n = stage['n']
    h = {1:1120, 2:1120, 3:1430, 4:1810}[n]
    auth = RED if n > 1 else MUTED
    out = [text(60, 65, f"0{n}  /  {stage['title']}", 43, weight=600), text(60, 110, stage['delta'], 25, MUTED)]
    if n == 1:
        out += [box(60,170,500,175,'Trusted JWT issuer',['Signs destination access tokens','Publishes public validation keys'],RED),
                box(710,170,530,175,'Provisioned credentials',['Bearer tokens in Kubernetes Secrets','Owner manages expiry and rotation'],RED),
                box(1370,170,490,175,'API trust and permission',['Trusted issuer and audience','Caller + operation allowlists'])]
    else:
        out += [box(60,170,500,175,'Microsoft Entra ID',['Federated workload authenticates','Entra issues destination access JWTs'],RED),
                box(710,170,530,175,'Trusted credential adapter',['Projected assertion → token exchange','SDK caches and reacquires on expiry'],RED),
                box(1370,170,490,175,'Federated trust + API grants',['AKS issuer + subject + audience','UAMI identity + destination grants'],RED)]
    out += [f'<rect x="380" y="410" width="1490" height="370" fill="#F9F9F7" stroke="{LINE}" stroke-width="2"/>',
            text(405, 450, 'Kubernetes service boundary',23,MUTED),
            edge('M310 345V390H185V510',auth,True),
            edge('M975 345V475H1115V510',auth,True),
            edge('M320 575H430'),edge('M780 550H920'),edge('M920 640H780'),
            edge('M680 685V755H1635V685'),edge('M500 685V815H320'),
            edge('M1660 685V815'),
            box(50,510,270,175,'API consumer',['Application workload','Agent API access JWT'],RED if n>1 else LINE),
            box(430,510,350,175,'Agent Gateway',['JWT validation + policy','Agent, tool, model routes'],RED),
            box(920,510,390,175,'Agent runtime',['Reviewed skills + instructions','Uses trusted adapter for auth']),
            box(1460,510,350,175,'MCP service',['Typed, bounded operations','Separate backend identity']),
            box(50,815,270,150,'Model garden',['Approved inference','LLM endpoints']),
            box(660,815,650,110,'Reviewed delivery',['Git + Flux + KRO · policies, agents, pinned skills']),
            box(1460,815,350,110,'Backend API / data',['MCP identity + grants']),
            edge('M1280 815V785H1240V685',MUTED,True),
            label(185,475,'Agent-API JWT',auth),label(1195,398,'Separate destination credentials',auth),
            label(375,556,'HTTPS'),label(850,533,'Invoke'),label(850,625,'Tool / model'),
            label(1135,741,'Authorized MCP route · destination token'),
            label(385,800,'Model route'),label(1730,780,'Backend token')]
    if n == 1:
        out += [text(60,1020,'Baseline choice',23,RED,600),
                text(290,1020,'Stored bearer tokens illustrate the starting point. JWT does not require Kubernetes Secret storage.',23),
                text(60,1063,'Validate signature, issuer, audience, time and permissions. Do not pass caller tokens to unrelated destinations.',23,MUTED)]
    else:
        out += [text(60,1020,'Identity change',23,RED,600),
                text(290,1020,'No stored client secret or provisioned bearer token for this federated path.',23),
                text(60,1063,'Short-lived assertions and access tokens still exist. Keep them outside prompts, tool results and telemetry.',23,MUTED)]
        out += [edge('M1615 170V145H310V170',RED,True),
                label(1030,140,'Configured federation trust',RED,size=20),
                edge('M560 230H710',RED,True),edge('M710 290H560',RED,True),
                label(635,269,'Exchange',RED,size=18)]
    if n >= 3:
        out.insert(7, edge('M605 685V790H1340V985H1890V1115H480V1170',BLUE,True)
                   +edge('M1310 600H1340V985',BLUE,True,False)
                   +edge('M1810 595H1890V985',BLUE,True,False))
        out += [label(1120,1140,'Gateway decisions + agent spans + MCP operations',BLUE),
                box(60,1170,780,180,'OpenTelemetry + Alloy',['Propagate trace context across instrumented hops','Filter credentials and approved metadata before export'],BLUE),
                box(990,1170,870,180,'LGTM observability',['Loki logs · Grafana dashboards · Tempo traces · Mimir metrics','Errors, latency, policy decisions and provider-reported usage'],BLUE),
                edge('M840 1255H990',BLUE,True),label(915,1230,'Export',BLUE),
                text(990,1400,'Telemetry describes execution. Evaluation judges behavior.',23,MUTED)]
    if n == 4:
        out += [box(60,1500,535,205,'Release evaluation',['Versioned candidate + cases + rubric','Functional, tool, security, quality checks','PASS / FAIL / UNKNOWN receipt'],GREEN),
                box(710,1500,535,205,'Runtime assessment',['Approved samples or replay cases','Expected outcomes + permitted evidence','Identity, data and spend limits'],GREEN),
                box(1360,1500,500,205,'Evidence + review',['Bind verdict to exact versions','Existing promotion approval','Findings → next reviewed revision'],GREEN),
                edge('M450 1350V1450H975V1500',GREEN,True),
                label(940,1475,'Approved evidence',GREEN),
                edge('M327 1705V1735H1610V1705',GREEN,True),label(975,1725,'Release receipt',GREEN),
                edge('M1245 1650H1360',GREEN,True),label(1302,1628,'Finding',GREEN,size=19),
                text(60,1765,'A release verdict informs the existing Git review and promotion process. It does not grant deployment permissions.',23,MUTED)]
    return shell(stage['title'], f"Proposed DICE architecture, stage {n}. {stage['intro']} Solid arrows show calls. Dashed arrows show credentials, telemetry or evidence.", h, ''.join(out))


def handshake():
    out = [text(60,65,'02a  /  The workload identity handshake',43,weight=600),
           text(60,110,'Direct AKS federation to a UAMI. The final access token is for the receiving API.',25,MUTED),
           box(60,170,400,135,'AKS service account',['Projected, rotating JWT assertion'],RED),
           box(570,170,420,135,'Trusted SDK / adapter',['Runs with the workload identity'],RED),
           box(1100,170,350,135,'Microsoft Entra ID',['Federated UAMI trust'],RED),
           box(1560,170,300,135,'Receiving API',['JWT + operation policy'],RED)]
    for x in (260,780,1275,1710):
        out.append(edge(f'M{x} 305V1010',LINE,True,False))
    rows = [
        (400,260,780,'1  Read the projected service-account assertion',RED),
        (520,780,1275,'2  Exchange assertion for destination access',RED),
        (750,1275,780,'3  Return a short-lived destination access token',RED),
        (880,780,1710,'4  Call the approved API with its access token',INK),
    ]
    for y,x1,x2,t,c in rows:
        out += [edge(f'M{x1} {y}H{x2}',c), label((x1+x2)/2,y-22,t,c,size=22)]
    out += [box(1070,565,430,125,'Entra verifies trust',['Issuer + subject + assertion aud','UAMI permissions for the API'],RED),
            box(1505,925,365,125,'API permission checks',['Signature, issuer, time, API aud','Required role or caller ACL']),
            box(60,1090,890,185,'Two audiences with different jobs',['Assertion aud = api://AzureADTokenExchange','Access-token aud = the registered destination API','Never use the federation assertion as the API bearer token'],RED),
            box(1010,1090,850,185,'What this removes from Kubernetes Secrets',['No static client secret or private signing key for this path','No manually provisioned destination bearer token','Projected assertion + access token remain sensitive'],RED),
            text(60,1332,'The SDK reacquires access as tokens expire. Restrict the adapter to approved destinations and registered workload identities.',23),
            text(60,1377,'Repeat with separate identities for caller, agent and MCP backend. This view does not imply Entra Agent ID or user delegation.',23,MUTED)]
    return shell('The workload identity handshake','Sequence showing direct AKS workload federation to a UAMI. A projected Kubernetes JWT is exchanged with Microsoft Entra for a destination-specific access JWT. Both remain sensitive credentials.',1425,''.join(out))


for stage in STAGES:
    (ROOT/stage['file']).write_text(overview(stage))
(ROOT/'02a-entra-handshake.svg').write_text(handshake())

sections = []
for stage in STAGES:
    svg = (ROOT/stage['file']).read_text().replace('id="title"',f'id="{stage["key"]}-title"').replace('id="desc"',f'id="{stage["key"]}-desc"').replace('aria-labelledby="title desc"',f'aria-labelledby="{stage["key"]}-title {stage["key"]}-desc"').replace('id="arrow"',f'id="{stage["key"]}-arrow"').replace('url(#arrow)',f'url(#{stage["key"]}-arrow)')
    notes = ''.join(f'<div><h3>{escape(title)}</h3><p>{escape(body)}</p></div>' for title,body in stage['points'])
    extra = ''
    if stage['n'] == 2:
        extra = f'''<details open><summary>The handshake, step by step</summary><p>This close-up uses direct federation. The assertion audience and the API audience are separate.</p><div class="diagram" tabindex="0" aria-label="Scrollable workload identity sequence diagram">{(ROOT/'02a-entra-handshake.svg').read_text().replace('id="title"','id="handshake-title"').replace('id="desc"','id="handshake-desc"').replace('aria-labelledby="title desc"','aria-labelledby="handshake-title handshake-desc"').replace('id="arrow"','id="handshake-arrow"').replace('url(#arrow)','url(#handshake-arrow)')}</div><a href="02a-entra-handshake.svg" download>Download the handshake SVG</a></details>'''
    sections.append(f'''<section id="{stage['key']}" class="stage"><div class="section-head"><span class="number">0{stage['n']}</span><div><p class="eyebrow">{escape(stage['delta'])}</p><h2>{escape(stage['title'])}</h2></div><a class="download" href="{stage['file']}" download>Download SVG ↗</a></div><p class="intro">{escape(stage['intro'])}</p><div class="legend"><span>→ Request or service call</span><span class="identity">⇢ Identity or credential relationship</span>{'<span class="telemetry">⇢ Telemetry</span>' if stage['n']>=3 else ''}{'<span class="eval">⇢ Evaluation evidence</span>' if stage['n']==4 else ''}</div><div class="diagram" tabindex="0" aria-label="Scrollable architecture diagram for stage {stage['n']}">{svg}</div><div class="notes">{notes}</div><aside class="presenter"><strong>Presenter cue</strong><p>{escape(stage['talk'])}</p></aside>{extra}</section>''')

html = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><link rel="icon" href="data:,"><title>DICE architecture · four progressive views</title><style>
:root{--paper:#F4F3EE;--ink:#1C1C1C;--muted:#555952;--line:#CCCABC;--red:#C72127;--blue:#245F86;--green:#28634B}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:105px}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:inherit;text-underline-offset:4px}a:focus-visible,summary:focus-visible,.diagram:focus-visible{outline:3px solid var(--red);outline-offset:4px}header,main,footer{max-width:1480px;margin:auto;padding:42px 42px}header{padding-top:62px;padding-bottom:35px}.eyebrow{font:12px/1.5 ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--red);margin:0 0 10px}h1{font:clamp(40px,5vw,68px)/1.08 Georgia,serif;letter-spacing:-.025em;margin:12px 0 24px;max-width:1000px}h1 em{color:var(--red);font-weight:400}.lede{font-size:20px;max-width:930px;margin-bottom:28px}.status{display:inline-block;border:1px solid var(--line);padding:6px 12px;font-size:13px;background:white}.key{border-left:4px solid var(--red);padding:14px 22px;background:white;max-width:1100px}.key p{margin:0}nav{position:sticky;top:0;z-index:2;background:var(--paper);border-block:1px solid var(--line)}nav .inner{display:flex;gap:8px;max-width:1480px;margin:auto;padding:12px 42px;overflow-x:auto}nav a{white-space:nowrap;text-decoration:none;font-size:14px;font-weight:600;padding:9px 14px;border:1px solid transparent}nav a:hover,nav a:focus{border-color:var(--line);background:white}main{padding-top:12px}.stage{padding:46px 0 54px;border-bottom:1px solid var(--line);scroll-margin-top:25px}.section-head{display:flex;gap:20px;align-items:center}.number{font:44px/1 Georgia,serif;color:var(--red);border-right:1px solid var(--line);padding-right:20px}h2{font:clamp(28px,3vw,39px)/1.2 Georgia,serif;letter-spacing:-.015em;margin:0}.section-head .eyebrow{font-size:11px;margin-bottom:8px}.download{margin-left:auto;white-space:nowrap;font-size:14px}.intro{font-size:18px;max-width:1120px;margin:24px 0}.legend{display:flex;flex-wrap:wrap;gap:12px 24px;font-size:12px;margin:18px 0 12px}.identity{color:var(--red)}.telemetry{color:var(--blue)}.eval{color:var(--green)}.diagram{overflow:auto;border:1px solid var(--line);background:var(--paper)}.diagram svg{display:block;width:100%;min-width:1050px;height:auto}.notes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 42px;margin-top:20px}.notes h3{font-size:16px;margin:18px 0 6px}.notes p{margin:0;color:var(--muted);font-size:15px;line-height:1.65}.presenter{border-left:3px solid var(--red);padding:14px 20px;background:white;margin-top:28px}.presenter strong{font:11px/1.5 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.07em;color:var(--red)}.presenter p{margin:7px 0 0;font-size:16px}details{margin-top:32px;border-top:1px solid var(--line);padding-top:24px}summary{font:25px/1.4 Georgia,serif;cursor:pointer}details>a{display:inline-block;margin-top:14px;font-size:14px}.compare{padding:46px 0}table{border-collapse:collapse;width:100%;font-size:14px;margin-top:22px}th,td{padding:14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{font-weight:600}.table-wrap{overflow:auto}th:first-child{width:16%}.sources{font-size:14px;border-top:1px solid var(--line);padding-top:36px}.sources h2{font-size:28px}.sources ul{padding-left:22px}.sources a{overflow-wrap:anywhere}.sources p{color:var(--muted);max-width:1050px}footer{padding-top:10px;padding-bottom:40px;font-size:12px;color:var(--muted)}
@media(max-width:700px){header,main,footer{padding-left:20px;padding-right:20px}header{padding-top:32px}.lede{font-size:18px}nav .inner{padding:8px 16px;gap:0}nav a{padding:10px;font-size:12px}.section-head{flex-wrap:wrap;gap:14px}.number{font-size:34px;padding-right:14px}.section-head>div{flex:1;min-width:200px}.download{margin:0 0 0 53px}.notes{grid-template-columns:1fr;gap:0}.stage{padding-top:35px}.intro{font-size:16px}.key{padding:13px 16px}table{min-width:760px}.legend{gap:6px 14px}.diagram svg{min-width:1050px}html{scroll-padding-top:82px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{@page{size:A3 landscape;margin:12mm}nav,.download{display:none}header,main,footer{max-width:none;padding:10px}.stage{break-before:page;padding-top:0;border:0}.diagram{overflow:visible;border:0}.diagram svg{min-width:0;width:100%;max-height:215mm}.notes{gap:4px 22px}.notes p,.presenter p{font-size:12px}.intro{font-size:14px}.presenter{margin-top:12px}details{break-before:page}.compare,.sources{break-before:page}h1{font-size:48px}}
</style></head><body><header><p class="eyebrow">DICE / architecture walkthrough / 12 November 2026</p><h1>One architecture.<br>Build it up <em>one layer at a time.</em></h1><p class="lede">Start with a protected agent request. Replace stored credentials with Microsoft Entra workload identity. Add visibility into execution, then evaluate the behavior.</p><p class="status">Proposed design for review · based on the 11 November SCD</p><div class="key"><p><strong>Entra still issues JWT access tokens for these APIs.</strong> The identity step changes how workloads acquire credentials. It removes stored client secrets for the federated path while retaining short-lived, sensitive tokens.</p></div></header><nav aria-label="Architecture views"><div class="inner"><a href="#jwt">01 · JWT</a><a href="#entra">02 · Entra ID</a><a href="#observability">03 · Observability</a><a href="#evaluation">04 · Evaluation</a><a href="#comparison">Compare views</a></div></nav><main>'''+''.join(sections)+'''
<section class="compare" id="comparison"><p class="eyebrow">What each view adds</p><h2>The request path stays consistent</h2><div class="table-wrap"><table><thead><tr><th>View</th><th>Credential path</th><th>Execution evidence</th><th>Behavior verdict</th></tr></thead><tbody><tr><th>01 · JWT</th><td>Provisioned destination JWTs. This baseline uses Secrets for in-cluster bearer credentials.</td><td>Local operational checks only. A correlated telemetry system is not shown.</td><td>No evaluation layer.</td></tr><tr><th>02 · Entra ID</th><td>Projected Kubernetes assertion → Entra exchange → destination token. No static client secret for this path.</td><td>Identity trust and API authorization remain separate checks.</td><td>No evaluation layer.</td></tr><tr><th>03 · Observability</th><td>Same federation as view 2.</td><td>Correlated traces, logs and metrics. Provider usage where available.</td><td>Telemetry alone cannot establish correctness.</td></tr><tr><th>04 · Evaluation</th><td>Same federation as view 2, with separately scoped evaluation identities.</td><td>Approved telemetry plus versioned cases, expectations and evidence.</td><td>Version-bound PASS, FAIL or UNKNOWN receipts feed existing review.</td></tr></tbody></table></div></section>
<section class="sources"><h2>Scope and source notes</h2><p>These diagrams explain a proposed design. They perform no authentication, telemetry collection, evaluation or deployment. The versions retain the gateway, agent, MCP, model garden and reviewed GitOps delivery from yesterday's overview. Registry and skill-catalog details remain in the SCD. This walkthrough does not change their ownership.</p><p>The Entra view selects direct AKS Workload Identity federation to a UAMI. It does not imply a distinct Entra Agent ID principal, a delegated user flow, or automatic identity propagation across the gateway. Those paths need their own identity binding, permissions and receiving-service support. Gateway routing does not itself grant downstream access.</p><p>The credential adapter is a trusted code component, not a model-callable tool that returns tokens. Model-controlled tools must not read its token mount or execute with its unrestricted identity. The receiving API enforces an application-role or explicit caller-ACL policy as well as JWT validation.</p><p>The initial JWT view illustrates manually provisioned tokens as a teaching baseline. JWT authentication can also use automatic token acquisition without Entra. The comparison is about the selected credential lifecycle, rather than a limitation of JWT.</p><ul><li><a href="https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview">Microsoft Learn · AKS Workload Identity overview</a><br>https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview</li><li><a href="https://learn.microsoft.com/en-us/azure/aks/workload-identity-deploy-cluster">Microsoft Learn · Configure workload federation</a><br>https://learn.microsoft.com/en-us/azure/aks/workload-identity-deploy-cluster</li><li><a href="https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens">Microsoft Learn · Access tokens and resource-server validation</a><br>https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens</li><li><a href="https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow">Microsoft Learn · Application permissions and caller ACLs</a><br>https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow</li></ul><p>Reviewed against Microsoft documentation on 12 November 2026. The diagrams use no real identities, credentials or environment addresses. The HTML is self-contained and can be shared by itself. The adjacent SVG files are separate vector exports.</p></section></main><footer>Use the navigation links to present each layer. On a narrow screen, scroll within a diagram or open its SVG. Use the browser's Print command for the full pack.</footer></body></html>'''
(ROOT/'index.html').write_text(html)
(ROOT/'README.md').write_text('''# DICE progressive architecture views

Open `index.html` for the complete offline walkthrough. The HTML embeds all five SVG diagrams and needs no network connection. The SVG exports can be inserted into architecture documents or slides.

1. `01-jwt.svg` shows a protected API, provisioned bearer JWTs, separate tool credentials and the shared service path.
2. `02-entra-workload-identity.svg` replaces provisioned credentials with direct AKS Workload Identity federation to a UAMI.
3. `02a-entra-handshake.svg` explains the projected assertion, Entra exchange and destination API validation.
4. `03-observability.svg` adds OpenTelemetry, Alloy and LGTM without changing the request path.
5. `04-evaluation.svg` adds release and runtime evaluation with version-bound receipts and existing promotion approval.

The diagrams describe a proposed design. This task performs no cluster, cloud, identity or delivery changes. The baseline illustrates Kubernetes Secret storage as one possible starting point, not a JWT requirement. Entra access tokens for the registered APIs remain JWTs. Federation removes static client secrets for the shown path, not all credentials from the pod.

Source is the 11 November DICE solution concept design and overview. Its original files are preserved. Microsoft identity references and the scope notes are included in the HTML.

Regenerate the document and SVG exports with `python3 build.py`. `build.py` is a local document-authoring helper, not a deployment component.

From this folder, open on macOS:

```sh
open -a "Google Chrome" "index.html"
```
''')
print('Wrote index.html, README.md and five SVG exports.')
