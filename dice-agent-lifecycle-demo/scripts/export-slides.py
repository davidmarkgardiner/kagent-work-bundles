"""Copy the existing offline DICE presentation closure into this work bundle."""
from collections import deque
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT.parent/'secure-kro-classic-kagent'
DEST=ROOT/'slides/previous'
class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.refs=[]
    def handle_starttag(self,tag,attrs):
        self.refs.extend(v for k,v in attrs if k in ('src','href') and v)

queue=deque(sorted(SOURCE.glob('*.html')))
seen=set();items=[]
while queue:
    source=queue.popleft().resolve()
    if source in seen:continue
    if len(seen)>350:raise SystemExit('Offline reference closure exceeds the reviewed size.')
    if not source.is_relative_to(SOURCE) or not source.is_file():
        raise SystemExit('Missing or outside-prepared-bundle reference: '+str(source))
    seen.add(source)
    relative=source.relative_to(SOURCE)
    target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
    items.append({'path':'slides/previous/'+relative.as_posix(),'sourcePath':'secure-kro-classic-kagent/'+relative.as_posix(),
                  'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    if source.suffix.lower()!='.html':continue
    links=Links();links.feed(source.read_text())
    for raw in links.refs:
        url=urlsplit(raw)
        if url.scheme or url.netloc or not url.path:continue
        linked=(source.parent/unquote(url.path)).resolve()
        if linked.is_dir():linked=linked/'index.html'
        queue.append(linked)

source_commit=subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()
managed=[]
for folder,name,label in [('managed-aks-platform-slides','index.html','Managed Kubernetes platform'),
                          ('managed-aks-two-slide-overview','managed-aks-two-slides.html','Managed Kubernetes overview')]:
    source=SOURCE.parent/folder/name
    if not source.is_file():continue
    target=ROOT/'slides/platform'/folder/name;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
    items.append({'path':str(target.relative_to(ROOT)),'sourcePath':folder+'/'+name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    managed.append((str(target.relative_to(ROOT/'slides')),label))

labels={'START-HERE.html':'Original complete demo menu','journey.html':'Secure agent journey',
        'showcase.html':'DICE showcase review sheets','resources.html':'Resources and hardening',
        'sre-lens.html':'SRE Lens specialists','triage.html':'Triage and recovery','sdlc.html':'Agent-assisted SDLC',
        'tomorrow.html':'Desired architecture and identity','presentation.html':'YAML explorer and simulated onboarding',
        'index.html':'Architecture deep dive','onboarding-dashboard.html':'Earlier onboarding simulation',
        'live-onboarding.html':'Live frontend source (requires its existing backend)'}
links=[('lifecycle.html','Terminal-first lifecycle presentation')]+[('previous/'+p.name,labels.get(p.name,p.stem)) for p in sorted(SOURCE.glob('*.html'))]+managed
cards=''.join('<a href="'+escape(path,quote=True)+'"><span>'+escape(label)+'</span><small>'+escape(path)+'</small></a>' for path,label in links)
index='''<!doctype html><html lang="en-GB"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>DICE presentation library</title><style>body{background:#F4F3EE;color:#1C1C1C;font:20px/1.5 Arial,Helvetica,sans-serif;margin:0;padding:5vw}main{max-width:1400px;margin:auto}h1{font-size:58px;font-weight:300;border-left:4px solid #E60000;padding-left:24px}p{max-width:1100px;color:#5A5D5C}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}a{display:block;background:white;border:1px solid #CCCABC;padding:22px;text-decoration:none;color:#1C1C1C}a:hover{border-color:#E60000}small{display:block;color:#5A5D5C;font-size:14px;margin-top:8px}</style><main><p>UK8S DICE / work presentation pack</p><h1>Present the journey. Show the evidence.</h1><p>Start with the terminal-first lifecycle deck. The earlier decks and their offline support files are copied into this folder. They retain their original simulations, dates and proof boundaries. Live observations come from the workplace terminal, Gateway, Grafana and OTel views.</p><p><a href="../architecture/index.html">Solution design, authentication and evaluation diagrams</a></p><div class="grid">'''+cards+'''</div><p>The live frontend source requires its approved backend. Opening a slide does not install services or execute a model. Use the written presenter walkthrough and command sheet for the actual demonstration.</p></main></html>'''
(ROOT/'slides/index.html').write_text(index)
manifest={'sourceRepository':'https://github.com/davidmarkgardiner/kagent-work-bundles','sourceCommit':source_commit,
          'scope':'Copied previously published presentation pages and their local HTML reference closure. Historical and illustrative labels retained.',
          'mainPresentations':len(links),'copiedFiles':len(items),'files':sorted(items,key=lambda x:x['path'])}
(ROOT/'slides/SOURCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'presentations':len(links),'copiedFiles':len(items),'sourceCommit':source_commit}))
