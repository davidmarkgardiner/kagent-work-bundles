"""Render the reviewed logical design as offline SVG sheets and an HTML viewer."""
from pathlib import Path
from html import escape
import re

ROOT=Path(__file__).resolve().parents[1]/'architecture'
ROOT.mkdir(exist_ok=True)
INK='#1C1C1C';GREY='#5A5D5C';RED='#E60000';PAPER='#F4F3EE';RULE='#CCCABC'

def start(title,w=1920,h=1180):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">DICE proposed target design. Solid arrows carry requests or content. Dashed arrows show identity, policy, delivery or telemetry relationships.</desc><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10Z" fill="context-stroke"/></marker></defs><rect width="100%" height="100%" fill="{PAPER}"/>']

def label(parts,x,y,text,size=22,color=GREY,anchor='start',masked=True):
    if color==RED:color='#DA0000'
    mask=f' data-wire-label="true" paint-order="stroke" stroke="{PAPER}" stroke-width="7" stroke-linejoin="round"' if masked else ''
    parts.append(f'<text{mask} x="{x}" y="{y}" fill="{color}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" text-anchor="{anchor}">{escape(text)}</text>')

def line(parts,path,dashed=False,color=INK):
    dash=' stroke-dasharray="9 7"' if dashed else ''
    parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.6"{dash} marker-end="url(#arrow)"/>')

def card(parts,x,y,w,h,title,rows,accent=False):
    parts.append('<g class="card">')
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white" stroke="{RULE}" stroke-width="2"/>')
    parts.append(f'<path d="M{x} {y} H{x+w}" stroke="{RED if accent else RULE}" stroke-width="{4 if accent else 2}"/>')
    label(parts,x+18,y+40,title,30,INK,masked=False)
    for i,row in enumerate(rows):label(parts,x+18,y+76+i*28,row,21,GREY,masked=False)
    parts.append('</g>')

def save(name,parts):
    text=''.join(parts)
    labels=re.findall(r'<text data-wire-label="true".*?</text>',text,flags=re.S)
    text=re.sub(r'<text data-wire-label="true".*?</text>','',text,flags=re.S)
    (ROOT/name).write_text(text+''.join(labels)+'</svg>\n')

p=start('DICE logical architecture')
p.append(f'<rect x="375" y="280" width="1510" height="620" rx="0" fill="#F9F9F7" stroke="{RULE}" stroke-width="2"/>')
label(p,395,315,'Kubernetes: approved runtime, service, identity and network boundaries',22)
line(p,'M170 380 V140 H450',False,RED);label(p,35,250,'Acquire a destination token',20,RED);label(p,35,278,'UAMI or interactive client',20,RED)
line(p,'M625 215 V380',True,RED);label(p,642,260,'Issuer / policy trust',20,RED)
line(p,'M1260 215 V265 H1500 V350',True,RED)
line(p,'M810 140 H855 V245 H1420 V350',True,RED)
label(p,1040,238,'Agent identity binding',20,RED)
line(p,'M1370 185 H1860 V760 H1840',True,RED)
line(p,'M1140 215 H1250 V745 H1235',True,RED)
line(p,'M1655 215 V350');label(p,1670,270,'Pinned skill release',20)
line(p,'M1430 110 H1370',True,RED)
line(p,'M310 465 H410');label(p,350,442,'HTTPS',20,INK,'middle')
line(p,'M710 465 H810');label(p,760,442,'Agent API',20,INK,'middle')
line(p,'M1150 420 H1370');label(p,1260,399,'Authorized invoke',20,INK,'middle')
line(p,'M1370 505 H1150');label(p,1260,487,'Model / MCP calls',20,INK,'middle')
line(p,'M850 550 V610 H175 V710');label(p,460,590,'Approved model route',21,INK)
line(p,'M175 850 V950')
line(p,'M1150 535 H1190 V620 H1605 V690');label(p,1420,605,'Agent identity + MCP audience',20,INK,'middle')
line(p,'M1060 690 V550',True,RED);label(p,1080,650,'Delivered policy',20,RED)
line(p,'M1235 800 H1335 V560 H1560 V550',True,RED)
line(p,'M1150 470 H1285 V935 H765 V980',True,GREY)
line(p,'M1840 460 H1880 V935 H765',True,GREY)
line(p,'M1840 775 H1880',True,GREY)
label(p,900,960,'OTel / Alloy collection from runtime, Gateway and MCP',20,GREY)
line(p,'M1230 1065 H1090',True,RED);label(p,1160,1040,'Verdicts',19,RED,'middle')
line(p,'M1550 980 V920 H1210 V860',True,RED);label(p,1310,915,'Release evaluation gate',20,RED)
card(p,450,65,360,150,'Microsoft Entra ID',['Caller UAMI / user identities','Agent ID / approved federation'],True)
card(p,920,65,450,150,'Central registry',['Agents · MCPs · skills · owners','Approved connections & evidence'])
card(p,1430,65,450,150,'GitLab skills',['Versioned SKILL.md + references','Reviewed immutable releases'])
card(p,30,380,280,170,'API consumer',['Application with UAMI','User / operator client'])
card(p,410,380,300,170,'Protected API',['VirtualService + JWT/','authorization policies','OR application validation'])
card(p,810,380,340,170,'Agent Gateway',['Agent front door','MCP and model routing','Identity / operation policy'],True)
card(p,1370,350,470,200,'Agent runtime',['Scoped workload and agent identity','Reviewed skills and instructions','Trusted credential adapter','Credentials outside model context'])
card(p,1370,690,470,140,'MCP services',['Typed, bounded operations','Separate backend identity'])
card(p,885,690,350,170,'GitOps delivery',['Definitions and policies in Git','Reviewed Flux reconciliation','KRO resource composition'])
card(p,40,710,270,140,'Model garden',['Existing approved','inference boundary'])
card(p,40,950,270,140,'LLM endpoints',['Approved models','Gateway/provider identity'])
card(p,440,980,650,155,'Observability',['OTel / Alloy → LGTM','Loki · Grafana · Tempo · Mimir','Correlated telemetry and reported usage'])
card(p,1230,980,650,155,'Evaluation',['Release gates + runtime assessments','Functional · tool · security · quality','Version-bound receipts and review'],True)
save('overview.svg',p)

p=start('DICE authentication flow',1920,1280)
actors=[(180,'API client',['UAMI / delegated profile']),(540,'Entra ID',['Token issuer']),(900,'API + Gateway',['JWT and route policy']),(1260,'Agent runtime',['Trusted credential adapter']),(1620,'MCP service',['Separate backend identity'])]
for x,title,rows in actors:
    p.append(f'<path d="M{x} 145 V1170" fill="none" stroke="{RULE}" stroke-width="2" stroke-dasharray="6 8"/>')
    card(p,x-150,20,300,120,title,rows)
steps=[(180,540,220,'1 Acquire agent-API token'),(540,180,300,'2 Token for agent API'),
       (180,900,400,'3 HTTPS invocation with caller token'),(900,1260,580,'5 Invoke the authorized agent'),
       (1260,540,690,'6 Adapter requests approved MCP-API access'),(540,1260,790,'7 Agent token for the MCP API'),
       (1260,900,890,'8 MCP operation and agent token'),(900,1620,990,'9 Authorize agent, audience and operation; forward'),
       (1620,900,1090,'10 Return bounded MCP result'),(900,1260,1170,'11 Return tool result to runtime')]
for a,b,y,text in steps:
    line(p,f'M{a} {y} H{b}',False,RED if y in (220,300,690,790) else INK)
    label(p,(a+b)/2,y-20,text,22,INK,'middle')
line(p,'M900 435 H1030 V500 H900',False,RED)
label(p,920,530,'4 Validate token and caller permission for this agent',22,RED)
label(p,40,1240,'The agent-API and MCP-API tokens have destination-specific audiences. Keep credentials out of prompts, logs and tool bodies.',22,GREY)
save('authentication.svg',p)

p=start('DICE evaluation and observability lifecycle',1920,870)
line(p,'M440 200 H560');line(p,'M1060 200 H1180');line(p,'M1540 200 H1640')
line(p,'M1760 300 V430');label(p,1740,380,'Approved revision',20,anchor='end')
line(p,'M1640 530 H1540');line(p,'M1180 530 H1060');label(p,1110,505,'OTel',20,GREY,'middle')
line(p,'M560 530 H440',True,RED);label(p,500,505,'Evidence',19,RED,'middle')
line(p,'M240 430 V340 H1360 V300',True,RED);label(p,690,327,'Version-bound verdicts feed the existing release review',22,RED)
line(p,'M240 660 V760 H700',True,RED);line(p,'M810 660 V710',True,GREY)
card(p,40,95,400,205,'Candidate release',['Agent and instruction version','Skill and MCP release','Model route and policy version','Evaluator and case version'])
card(p,560,95,500,205,'Release evaluations',['Contract and task behavior','Native skill and tool accuracy','Identity and isolation checks','Limits, errors and model compatibility'],True)
card(p,1180,95,360,205,'Evaluation receipt',['Exact candidate binding','Scores + hard policy gates','Evidence and provenance','PASS / FAIL / UNKNOWN'])
card(p,1640,95,240,205,'Release review',['Existing approval','Promotion policy','No automatic','production writes'])
card(p,1640,430,240,230,'Flux + KRO',['Apply reviewed','agent and policy','revision; verify','convergence'])
card(p,1180,430,360,230,'Running agent',['Protected API requests','Approved skill/MCP/model use','Native outcome receipts','Correlated operations'])
card(p,560,430,500,230,'Observability',['OTel / Alloy into LGTM','Traces · logs · metrics','Reported usage and cost provenance','Metadata-first collection'])
card(p,40,430,400,230,'Runtime evaluation',['Approved cases or samples','Own data/identity/spend scope','Functional and security results','Findings feed operations review'],True)
card(p,700,710,1180,115,'Central registry and evidence store',['Bind release, policy, tool, model and evaluator versions to their acceptance receipts.'])
save('evaluation.svg',p)

page='''<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>DICE solution design and authentication</title><style>*{box-sizing:border-box}body{margin:0;background:#F4F3EE;color:#1C1C1C;font:18px/1.5 Arial,Helvetica,sans-serif}header,nav,main{max-width:1920px;margin:auto;padding:18px 3vw}h1{font-size:40px;font-weight:300;margin:4px 0;border-left:4px solid #E60000;padding-left:20px}p{color:#5A5D5C;margin:8px 0}nav{display:flex;gap:10px;flex-wrap:wrap;border-top:1px solid #CCCABC;border-bottom:1px solid #CCCABC}button,a{font:17px Arial;color:#1C1C1C;background:white;border:1px solid #CCCABC;padding:11px 15px;text-decoration:none;cursor:pointer}button[aria-selected="true"]{border-bottom:3px solid #E60000}button:focus-visible,a:focus-visible{outline:2px solid #E60000}.sheet{display:none}.sheet.active{display:block}h2{font-size:28px;font-weight:400}.sheet img{display:block;width:100%;height:auto;background:#F4F3EE}.caption{max-width:1500px;font-size:20px}.note{border-left:3px solid #E60000;padding-left:18px}footer{padding:20px 3vw;border-top:1px solid #CCCABC;color:#5A5D5C}@media print{@page{size:A3 landscape;margin:8mm}header,nav,footer{display:none}main{padding:0}.sheet,.sheet.active{display:block;page-break-after:always}h2{font-size:24px}.sheet img{max-height:220mm;width:100%;object-fit:contain}.caption{font-size:14px}body{print-color-adjust:exact;-webkit-print-color-adjust:exact}}</style></head><body><header><p>UK8S DICE / solution concept design and ADR</p><h1>Identity, execution and evidence.</h1><p class="note">Proposed target design. Solid arrows carry calls/content; dashed arrows show identity, governance, delivery or telemetry. Workplace acceptance remains separate.</p></header><nav aria-label="Design views"><button data-view="overview" aria-selected="true">Architecture overview</button><button data-view="authentication" aria-selected="false">Authentication flow</button><button data-view="evaluation" aria-selected="false">Evaluation and observability</button><a href="SCD.md">Read SCD</a><a href="ADR-0001.md">Read ADR</a><a href="PRESENTER-NOTES.md">Speaker notes</a><a href="../slides/index.html">All presentation slides</a><button id="print">Print all views</button></nav><main><section class="sheet active" id="overview"><h2>The agent, tools and model garden behind controlled routes</h2><p class="caption">Entra supplies destination tokens. The API and Gateway authorize their use. Agents and MCPs have separate workload/backend identities and central registry records. GitLab publishes reviewed skills. Evaluations sit beside OTel/LGTM and gate reviewed releases.</p><img src="overview.svg" alt="DICE overview with Entra, client, API exposure, Agent Gateway, Kubernetes agents and MCPs, GitLab skills, central registry, model garden and LLMs, observability and evaluations"><p><a href="overview.svg">Open vector diagram</a></p></section><section class="sheet" id="authentication"><h2>Caller-to-agent and agent-to-MCP are separate token paths</h2><p class="caption">A calling workload uses its UAMI; a human uses an approved interactive client. The agent's trusted credential adapter acquires the MCP API token using the selected Agent ID or per-agent identity profile. API validation can sit with Istio or in application code. Destination audiences and permissions still apply.</p><img src="authentication.svg" alt="Numbered token and authorization sequence from application to Entra to Gateway and agent, then from the agent through Entra and Gateway to MCP"><p><a href="authentication.svg">Open vector diagram</a></p></section><section class="sheet" id="evaluation"><h2>Evaluate the release, observe the runtime, assess the outcome</h2><p class="caption">Functional, tool, security and model checks bind to the exact release. Existing approval controls promotion. Runtime evaluation uses approved data and permissions beside metadata-first telemetry. Registry records retain the evidence.</p><img src="evaluation.svg" alt="Release evaluation gates before Flux and KRO, with runtime evaluation beside observability and evidence in the registry"><p><a href="evaluation.svg">Open vector diagram</a></p></section></main><footer>Use the presenter walkthrough for the live demonstration. These diagrams describe the target design and perform no authentication, registration, evaluation or deployment.</footer><script>const tabs=[...document.querySelectorAll('[data-view]')];function show(id){document.querySelectorAll('.sheet').forEach(s=>s.classList.toggle('active',s.id===id));tabs.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.view===id)));history.replaceState(null,'','#'+id)}tabs.forEach(t=>t.addEventListener('click',()=>show(t.dataset.view)));document.querySelector('#print').onclick=()=>window.print();function readHash(){if(tabs.some(t=>'#'+t.dataset.view===location.hash))show(location.hash.slice(1))}window.addEventListener('hashchange',readHash);readHash();</script></body></html>'''
for name in ('overview','authentication','evaluation'):
    svg=(ROOT/(name+'.svg')).read_text()
    svg=svg.replace('aria-labelledby="title desc"',f'aria-labelledby="{name}-title {name}-desc"')
    for ident in ('title','desc','arrow'):
        svg=svg.replace('id="'+ident+'"','id="'+name+'-'+ident+'"').replace('url(#'+ident+')','url(#'+name+'-'+ident+')')
    page=re.sub(r'<img src="'+name+r'\.svg"[^>]*>',lambda _:svg,page)
page=page.replace('.sheet img','.sheet svg')
(ROOT/'index.html').write_text(page)
print('Built three offline SVG design sheets and the HTML viewer.')
