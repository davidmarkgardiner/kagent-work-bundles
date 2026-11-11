"""Assemble a narration-timed HyperFrames edit from recorded screens and evidence."""
from pathlib import Path
import json,re,html
root=Path(__file__).resolve().parent
(root/'compositions').mkdir(exist_ok=True)
transcript=json.loads((root/'transcript.json').read_text())
words=transcript['words']
paragraphs=(root/'NARRATION.md').read_text().strip().split('\n\n')
normal=[re.sub(r'[^a-z0-9]','',x['text'].lower()) for x in words]
starts=[]
for para in paragraphs:
 needle=[re.sub(r'[^a-z0-9]','',x.lower()) for x in para.split()[:6]]
 matches=[i for i in range(len(normal)-len(needle)) if normal[i:i+len(needle)]==needle]
 if not matches:raise ValueError('Cannot align paragraph '+para[:40])
 starts.append(words[matches[0]]['start'])
end=302.05
scenes=[
 ('01','The running agent','Recorded screens · actual native task and tool results','intro'),
 ('02','The delivery contract','Contract walkthrough · recording instance was applied directly','delivery'),
 ('03','Open the live gateway','Externally managed routes · routing alone is not enforcement proof','gateway'),
 ('04','Open the agent interface','Dedicated recording agent · existing approved MiniMax route','runtime'),
 ('05','Watch the skill and tool calls','Actual execution · synthetic MCP status data · documentation-only analysis','tools'),
 ('06','Versioned guidance. Explicit tools.','Workplace GitLab source design · reviewed home-lab content mounts','skills'),
 ('07','Inspect the observed runtime','Native task completed · two HTTP discovery spans returned 404','otel'),
 ('08','Test the protected route','Observed HTTP 401 · separate MCP route · no Entra claim','security'),
 ('09','Inspect Entra Agent ID','Portal inspection · token exchange and enforcement remain separate','identity'),
 ('10','An API teams can consume','Declare · connect · observe · preserve the evidence','close')
]
css='''*{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden;font-family:Arial,Helvetica,sans-serif;background:#F4F3EE;color:#1C1C1C}#root{position:relative;width:100%;height:100%;overflow:hidden;background:#F4F3EE}.ground{position:absolute;inset:0;background:#F4F3EE}.top{position:absolute;left:64px;right:64px;top:35px;height:75px;border-bottom:1px solid #CCCABC;display:flex;align-items:center;gap:26px}.number{font-size:28px;color:#E60000}.title{font-size:42px;font-weight:400;margin:0}.brand{margin-left:auto;font-size:28px;color:#5A5D5C;letter-spacing:2px}.screen{position:absolute;left:64px;top:132px;width:1792px;height:840px;overflow:hidden;background:#FFF;border:1px solid #CCCABC}.screen video,.screen img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}.footer{position:absolute;left:64px;right:64px;top:997px;font-size:28px;color:#5A5D5C}.big{font-size:82px;font-weight:300;line-height:1.08;letter-spacing:-2px;margin:0 0 28px}.sub{font-size:30px;line-height:1.42;color:#5A5D5C;margin:0}.red{color:#E60000}.hero{position:absolute;left:94px;top:230px;width:770px;border-left:5px solid #E60000;padding-left:32px}.aside{position:absolute;left:970px;top:185px;width:840px;height:720px;overflow:hidden;background:#FFF;border:1px solid #CCCABC}.aside img{width:100%;height:100%;object-fit:cover;object-position:66% 35%}.paper{position:absolute;left:80px;right:80px;top:150px;bottom:130px}.columns{display:flex;gap:65px}.col{flex:1;min-width:0}.eyebrow{font-size:28px;letter-spacing:1px;color:#5A5D5C;text-transform:uppercase;margin:0 0 22px}.code{font-family:monospace;font-size:29px;line-height:1.52;white-space:pre-wrap;margin:0}.panel{background:#FFF;padding:35px;border-top:2px solid #CCCABC}.flow{display:flex;align-items:center;gap:20px;margin-top:52px}.flow span{font-size:29px;padding:20px 24px;background:white;border-bottom:2px solid #E60000}.flow b{font-size:32px;font-weight:400;color:#E60000}.rule{height:3px;background:#E60000;width:100%;margin:38px 0}.note{font-size:28px;line-height:1.45;color:#5A5D5C}.focus{position:absolute;inset:0;overflow:hidden}.focus img{width:2688px;height:1512px;max-width:none;object-fit:fill;left:-490px;top:-130px}.inset{z-index:3;position:absolute;right:0;bottom:0;background:#F4F3EE;padding:20px 25px;border-left:3px solid #E60000;font-size:28px;max-width:620px;line-height:1.4}.status{font-size:105px;font-weight:300;color:#E60000;margin:0 0 35px}.identity-crop{position:absolute;inset:0;overflow:hidden}.identity-crop img{width:1792px;height:1008px;object-fit:cover;top:-38px}.identity-band{position:absolute;left:0;right:0;bottom:0;background:#FFF;padding:24px;font-size:28px;line-height:1.45;border-top:1px solid #CCCABC}.close-result{font-family:monospace;font-size:28px;line-height:1.48;background:white;padding:34px;border-left:3px solid #E60000;margin-top:28px}.caption-guard{position:absolute;left:0;right:0;bottom:0;height:5px;background:#E60000;transform-origin:left center}'''
for i,(ident,title,note,kind) in enumerate(scenes):
 start=starts[i];stop=starts[i+1] if i+1<len(starts) else end;duration=stop-start
 cid='scene-'+ident
 body=''
 if kind=='intro':
  body='<div class="hero"><p class="eyebrow">A technical walkthrough</p><h2 class="big">Follow the<br>running agent.</h2><p class="sub">The gateway. The skills and tools.<br>The operations we can observe.</p><div class="rule"></div><p class="note">A recorded tour of UK8S DICE.</p></div><div class="aside"><img src="assets/images/skill-result.png" alt="Actual agent skill result"></div>'
 elif kind=='delivery':
  text='apiVersion: demo.kagent.dev/v1alpha1\nkind: ClassicSecureAgent\nmetadata:\n  name: demo\n  namespace: classic-agents\nspec:\n  modelConfig: approved-model\n  systemPrompt: Read the approved namespace\n  skills: [work-guidance]\n  tools: [kubernetes-readonly]'
  body='<div class="paper columns"><div class="col panel"><p class="eyebrow">Existing KRO bundle · owner contract excerpt</p><pre class="code">'+html.escape(text)+'</pre></div><div class="col"><h2 class="big">Reviewed intent<br>becomes runtime.</h2><p class="sub">Git contains the agent request<br>and the platform policies.</p><div class="flow"><span>Git</span><b>›</b><span>Flux</span><b>›</b><span>KRO</span></div><div class="rule"></div><p class="note">The recording instance is a direct rehearsal deployment.<br>This diagram explains the reusable delivery contract.</p></div></div>'
 elif kind=='gateway':
  body='<div class="screen"><video id="'+cid+'-video" class="clip" data-start="0" data-duration="'+str(duration)+'" data-track-index="0" src="assets/footage/gateway.mp4" muted playsinline></video><img id="'+cid+'-routes" class="clip" data-start="17" data-duration="'+str(duration-17)+'" data-track-index="1" src="assets/images/gateway-routes.png" alt="Actual gateway routes"></div>'
 elif kind=='runtime':
  body='<div class="screen"><video id="'+cid+'-video" class="clip" data-start="0" data-duration="'+str(duration)+'" data-track-index="0" src="assets/footage/runtime.mp4" muted playsinline></video></div>'
 elif kind=='tools':
  body='<div class="screen"><div class="focus"><img data-layout-allow-overflow="true" id="'+cid+'-image" src="assets/images/skill-result.png" alt="Actual successful skill load in the agent conversation"><img id="'+cid+'-mcp" class="clip" data-start="18" data-duration="'+str(duration-18)+'" data-track-index="1" data-layout-allow-overflow="true" src="assets/images/mcp-result.png" alt="Actual MCP execution result"></div><div id="'+cid+'-result" class="inset">Native task records<br><b>skills → read_file → read_file → get_demo_status</b><br>All four calls returned results.</div><video id="'+cid+'-terminal" class="clip" data-start="27" data-duration="'+str(duration-27)+'" data-media-start="10" data-track-index="2" style="z-index:4" src="assets/footage/terminal.mp4" muted playsinline></video></div>'
 elif kind=='skills':
  body='<div class="paper columns"><div class="col"><p class="eyebrow">Reviewed instruction package</p><h2 class="big">The skill guides<br>the investigation.</h2><div class="panel"><pre class="code">/skills/aks-known-issues/\n  SKILL.md\n  references/error-code-map.md\n\n/knowledge/aks-bootstrap/\n  oras-pull-unauthorized.md</pre></div></div><div class="col"><p class="eyebrow">Actual attached MCP operation</p><div class="panel"><pre class="code">get_demo_status()\n\ncaseCode: bootstrap-registry\nstatus: available\nsource: synthetic demo record</pre></div><div class="rule"></div><p class="sub">Versioned guidance and tool permission<br>are separate responsibilities.</p><p class="note">GitLab is the workplace source design.<br>The home-lab source is a separate Git fixture.</p></div></div>'
 elif kind=='otel':
  body='<div class="screen"><video id="'+cid+'-video" class="clip" data-start="0" data-duration="'+str(duration)+'" data-track-index="0" src="assets/footage/otel.mp4" muted playsinline></video><img id="'+cid+'-detail" class="clip" data-start="12" data-duration="'+str(duration-12)+'" data-track-index="1" src="assets/images/otel-trace-detail.png" alt="Actual native trace details, token usage, cost status and model-call timeline"></div>'
 elif kind=='security':
  body='<div class="paper columns"><div class="col panel"><p class="eyebrow">Actual unauthenticated MCP request</p><pre class="code">POST /hitl/mcp\nMCP initialize\nNo credential supplied</pre><div class="rule"></div><div class="status">HTTP 401</div><pre class="code">api key authentication failure:\nno API Key found</pre></div><div class="col"><h2 class="big">Prove the<br>specific boundary.</h2><p class="sub">This protected route rejects<br>the unauthenticated request.</p><div class="rule"></div><p class="note">Entra identity binding is a separate check.<br>Direct backend bypass is a separate check.<br>Network isolation needs actual traffic evidence.</p></div></div>'
 elif kind=='identity':
  body='<div class="screen"><video id="identity-video" class="clip" data-start="0" data-duration="43.38" data-track-index="0" src="assets/footage/entra.mp4" muted playsinline></video><div class="identity-band">Caller → agent API <span class="red">|</span> Agent identity → MCP API<br>Identity, audience and permission must match the destination. Token enforcement was not exercised in this runtime recording.</div></div>'
 elif kind=='close':
  body='<div class="paper"><p class="eyebrow">UK8S DICE</p><h2 class="big">Declare the agent.<br>Consume the API.</h2><div class="flow"><span>Approved capabilities</span><b>›</b><span>Running API</span><b>›</b><span>Observable evidence</span></div><div class="close-result">Observed: 1 skill load · 2 document reads · 1 MCP operation<br>Preserved: native task, tool results, MCP execution ID and OTel spans</div><p class="note">Next proof boundary: a fresh GitOps/KRO capture with the receiving environment’s identity and network controls.</p></div>'
 body=body.replace('data-duration="43.38"','data-duration="'+str(duration)+'"')
 template='<!doctype html><html><template><style>'+css+'</style><div id="root" data-composition-id="'+cid+'" data-width="1920" data-height="1080" data-duration="'+str(duration)+'"><div class="ground"></div><div class="top"><span class="number">'+ident+'</span><h1 class="title">'+title+'</h1><span class="brand">UK8S DICE</span></div>'+body+'<div class="footer">'+note+'</div></div><script>const tl=gsap.timeline({paused:true});tl.fromTo("#root .top",{opacity:0},{opacity:1,duration:0.2},0);const content=document.querySelector("#root .hero, #root .paper");if(content)tl.fromTo(content,{y:18,opacity:0},{y:0,opacity:1,duration:0.6,ease:"power3.out"},0.05);window.__timelines["'+cid+'"]=tl;</script></template></html>'
 (root/'compositions'/(cid+'.html')).write_text(template)
main='<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=1920,height=1080"><script src="assets/gsap.min.js"></script><style>html,body{margin:0;width:1920px;height:1080px;background:#F4F3EE;overflow:hidden}#root{width:100%;height:100%;position:relative}.host{position:absolute;inset:0}.progress{position:absolute;left:0;bottom:0;width:1920px;height:4px;background:#E60000;transform-origin:left center;z-index:30}</style></head><body><div id="root" data-composition-id="main" data-width="1920" data-height="1080" data-duration="'+str(end)+'" data-fps="24">'
for i,s in enumerate(scenes):
 stop=starts[i+1] if i+1<len(starts) else end
 main+='<div id="scene-'+s[0]+'" data-composition-id="scene-'+s[0]+'" class="clip host" data-start="'+str(starts[i])+'" data-duration="'+str(stop-starts[i])+'" data-track-index="0" data-track-kind="graphics" data-composition-src="compositions/scene-'+s[0]+'.html"></div>'
main+='<audio id="narration" class="clip" data-start="0" data-duration="'+str(end)+'" data-track-index="1" data-volume="1" src="assets/narration-leveled.m4a"></audio><div class="progress"></div></div><script>const tl=gsap.timeline({paused:true});tl.fromTo(".progress",{scaleX:0},{scaleX:1,duration:'+str(end)+',ease:"none"},0);window.__timelines["main"]=tl;</script></body></html>'
(root/'index.html').write_text(main)
(root/'edit-manifest.json').write_text(json.dumps({'duration':end,'fps':24,'scenes':[{'id':s[0],'title':s[1],'start':starts[i],'end':starts[i+1] if i+1<len(starts) else end,'kind':s[3]} for i,s in enumerate(scenes)]},indent=2)+'\n')
# Captions use the verified script's words and the returned speech timing.
caps=[]
for n in range(0,len(words),9):
 chunk=words[n:n+9];caps.append((chunk[0]['start'],chunk[-1]['end'],' '.join(x['text'] for x in chunk)))
out=[]
for i,(a,b,text) in enumerate(caps,1):
 stamp=[]
 for value in [a,b]:
  ms=round(value*1000);stamp.append(f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}')
 out.append(str(i)+'\n'+stamp[0]+' --> '+stamp[1]+'\n'+text+'\n')
(root/'captions.srt').write_text('\n'.join(out))
(root/'STORYBOARD.md').write_text('# Recorded DICE runtime walkthrough\n\nNarration drives the edit. Recorded screens are distinct from the delivery-contract explanation.\n\n'+'\n'.join(f'## Frame {i+1}: {s[1]}\n\n- src: compositions/scene-{s[0]}.html\n- start: {starts[i]}\n- end: {starts[i+1] if i+1<len(starts) else end}\n- evidence: {s[2]}\n- treatment: actual screen crop or evidence panel; restrained title entry and hard cuts\n' for i,s in enumerate(scenes)))
print('Built 10 narration-aligned scenes, captions and edit manifest.')
