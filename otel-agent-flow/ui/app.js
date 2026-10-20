const $ = id => document.getElementById(id);
const workflowPrompts={
  triage:'DEMO_WORKFLOW=triage. Call get_kubernetes_workloads, query_grafana_alerts, then get_gitlab_issue. Correlate the simulated symptoms and propose a read-only triage plan. Do not change the cluster or create an issue.',
  sdlc:'DEMO_WORKFLOW=sdlc. Call get_gitlab_issue, get_gitlab_pipeline, then review_change. Explain the simulated failed pipeline and review decision. Do not trigger a pipeline, write to GitLab, or deploy.',
  'identity-isolation':'DEMO_WORKFLOW=identity-isolation. Call read_team_a_resource, attempt_cross_team_resource, then read_team_b_resource. Explain the simulated allow/deny decisions. This is a policy simulation without Entra tokens, not proof of Entra isolation.',
  inventory:'DEMO_WORKFLOW=inventory. Call get_inventory_status, then get_recent_alerts. Summarize the simulated inventory health and identify the fixture data.',
  'change-review':'DEMO_WORKFLOW=change-review. Call get_inventory_status, then review_change. Explain the simulated change decision. Do not deploy or modify anything.',
  'dependency-failure':'DEMO_WORKFLOW=dependency-failure. Call check_dependency and explain its intentional simulated failure and a safe next step. Do not retry or modify anything.'
};
$('workflow').onchange=()=>{const prompt=state.runtime?.scenarios?.find(s=>s.id===$('workflow').value)?.prompt||workflowPrompts[$('workflow').value];if(prompt){$('prompt').value=prompt;$('prompt').oninput();}};
const runtimeModes={
  fixture:'Fixture model + simulated tools. Real kagent, Substrate, gateway, HTTP traffic, and OTel exports.',
  live:'Live model. Workflow tools return explicitly simulated data.',
  'live-tools':'Live model and real read-only Kubernetes and GitLab MCP data. OTel shows received calls.',
  connected:'Existing agent and its configured model, gateway, and tools. Activity appears only when OTel is received.'
};
const svgNS = 'http://www.w3.org/2000/svg';
const layout = {
  client: {x:35,y:145,label:'Caller',sub:'Agent prompt request',icon:'M18 17l7 7-7 7m10 0h8'},
  kagent: {x:285,y:145,label:'kagent',sub:'Agent runtime',icon:'M18 13v24m1-11 15-13m-15 13 15 11'},
  agentgateway: {x:550,y:45,label:'agentgateway',sub:'LLM routing',icon:'M17 16h20v20H17zM11 22h6m20 0h6M11 30h6m20 0h6'},
  model: {x:815,y:45,label:'Model provider',sub:'Tokens + response',icon:'M17 16h19v20H17zM22 21h9v9h-9z'},
  mcp: {x:550,y:245,label:'MCP tools',sub:'Allowlisted read operations',icon:'M18 17l-7 10 7 10m15-20 7 10-7 10m-7-23-4 26'},
  substrate: {x:285,y:385,label:'Agent Substrate',sub:'No local runtime',icon:'M13 20l13-7 13 7-13 7zM13 27l13 7 13-7m-26 7 13 7 13-7'},
  worker: {x:550,y:385,label:'Worker pool',sub:'No runtime telemetry',icon:'M13 16h27v8H13zm0 15h27v8H13zM18 20h1m-1 15h1'},
  actor: {x:815,y:385,label:'Sandbox actor',sub:'No runtime telemetry',icon:'M15 21l12-8 12 8v16H15zM22 37V26h10v11'},
};
const expectedEdges = [['client','kagent'],['kagent','agentgateway'],['agentgateway','model'],['kagent','mcp'],['kagent','substrate'],['substrate','worker'],['worker','actor']];
let state = {traces:[]}, selectedId = null, filter = null, follow = true, initial = true;
let seen = new Set(), activeNodes = new Map(), activeEdges = new Map(), replayTimers = [], replaying = false;
let manualPrices = null, lastRevision = -1;
const activeOperations=new Map();
let showInternal = false;
let logsPaused = false, logData = null;
let submitting = false, pendingTraceId = null;
const views = {visual: {panel:'visual-view', description:'Follow the observed request path and inspect its spans.'},logs: {panel:'logs-view', description:'Inspect API calls, status codes, and GenAI events. Select a trace ID to open its visual flow.'}};
function setView(view, focus=false){
  if(!Object.hasOwn(views,view))view='visual';
  for(const [id,config] of Object.entries(views)){
    $(config.panel).hidden=id!==view;
    $(`tab-${id}`).setAttribute('aria-selected',String(id===view));
    $(`tab-${id}`).tabIndex=id===view?0:-1;
  }
  $('view-description').textContent=views[view].description;
  history.replaceState(null,'',`#${view}`);
  if(view==='logs'){stopReplay();render();}
  if(focus)$(`tab-${view}`).focus();
}
for(const id of Object.keys(views)){
  $(`tab-${id}`).onclick=()=>setView(id);
  $(`tab-${id}`).onkeydown=event=>{
    const keys={ArrowLeft:'visual',ArrowRight:'logs',Home:'visual',End:'logs'};
    if(keys[event.key]){event.preventDefault();setView(keys[event.key],true);}
  };
}
function el(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; }
function svgel(tag, attrs) {const e = document.createElementNS(svgNS,tag);for (const [key,value] of Object.entries(attrs))e.setAttribute(key,value);return e;}
function selected() { return state.traces.find(t=>t.traceId===selectedId); }
function sessionGraph(){return !replaying&&selectedId===state.invocation?.traceId?state.sessionActivity:null;}
$('session-flow').onclick=()=>{stopReplay();follow=false;filter=null;selectedId=state.invocation?.traceId;render();};
function time(ms) {return ms>=1000 ? `${(ms/1000).toFixed(2)} s` : `${ms.toFixed(1)} ms`;}
function money(value) {return value===null || value===undefined ? 'Not reported' : `$${value.toFixed(6)}`;}
function count(value) {return value===null || value===undefined ? '—' : value.toLocaleString();}
function route(from,to) {
  const a=layout[from],b=layout[to];if(!a||!b)return '';
  if (a.y===b.y)return `M${a.x+185} ${a.y+40} L${b.x} ${b.y+40}`;
  if(from==='kagent'&&to==='substrate')return `M${a.x+92} ${a.y+80} L${b.x+92} ${b.y}`;
  return `M${a.x+185} ${a.y+40} C${a.x+225} ${a.y+40},${b.x-45} ${b.y+40},${b.x} ${b.y+40}`;
}
function buildMap() {
  for(const [id,n] of Object.entries(layout)){
    const g=svgel('g',{id:`node-${id}`,class:'node',tabindex:'0',role:'button','aria-label':`Inspect ${n.label}`,transform:`translate(${n.x},${n.y})`});
    g.append(svgel('rect',{class:'box',width:185,height:80,rx:12}));
    const icon=svgel('path',{class:'icon',d:n.icon,transform:'translate(2,14) scale(.82)'});g.append(icon);
    const title=svgel('text',{class:'label',x:52,y:33});title.textContent=n.label;g.append(title);
    const sub=svgel('text',{class:'sub',x:52,y:52,id:`sub-${id}`});sub.textContent=n.sub;g.append(sub);
    const choose=()=>{filter=id;renderTimeline();drawMap();};g.addEventListener('click',choose);g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});$('nodes').append(g);
  }
}
function drawMap() {
  const t=sessionGraph()||selected();const nodes=new Set(t?.components||[]), observed=new Map((t?.edges||[]).map(e=>[`${e.from}-${e.to}`,e]));
  $('graph-scope').textContent=sessionGraph()?'Observed in this session':'Observed in selected trace';
  const all=new Map(expectedEdges.map(e=>[e.join('-'),e]));for(const e of t?.edges||[])all.set(`${e.from}-${e.to}`,[e.from,e.to]);
  $('edges').replaceChildren();const now=Date.now();
  for(const [key,[from,to]] of all){
    const p=svgel('path',{d:route(from,to),class:`edge${observed.has(key)?' observed':''}${(activeEdges.get(key)||0)>now?' active':''}`,'marker-end':'url(#arrow)'});
    const title=svgel('title',{});title.textContent=observed.has(key)?`${from} → ${to}: ${observed.get(key).basis}`:'No traffic observed';p.append(title);$('edges').append(p);
  }
  for(const id of Object.keys(layout)){
    const node=$(`node-${id}`);node.setAttribute('class',`node${nodes.has(id)?' observed':' absent'}${(activeNodes.get(id)||0)>now?' active':''}${filter===id?' selected':''}`);
    $(`sub-${id}`).textContent=nodes.has(id)?sessionGraph()?'Observed in this session':'Observed in this trace':layout[id].sub;
  }
  const activeMcpServices=new Set(scopedSpans().filter(s=>s.toolExecution&&(activeOperations.get(`${s.traceId}/${s.spanId}`)||0)>now).map(s=>s.service));
  for(const card of document.querySelectorAll('.operation-card, .mcp-server'))card.classList.toggle('active',card.dataset.service?activeMcpServices.has(card.dataset.service):(activeOperations.get(card.dataset.spanKey)||0)>now);
  const hasSubstrate=state.traces.some(t=>t.components.some(c=>['substrate','worker','actor'].includes(c)));
  $('substrate-note').textContent=hasSubstrate?'Native runtime spans received. Session workflow includes related lifecycle traces. Trace details and token counts below stay scoped to the selected trace.':state.runtime?.substrateInstalled?'Installed in this cluster. Waiting for native runtime spans.':'Not installed in this local cluster. Its worker and actor lane stays inactive until runtime spans arrive.';
  if(state.runtime?.substrateInstalled&&!nodes.has('substrate'))$('sub-substrate').textContent='Waiting in this trace';
}
function scopedSpans(){
  const scope=sessionGraph();
  return scope?state.traces.filter(t=>scope.traceIds.includes(t.traceId)).flatMap(t=>t.spans):selected()?.spans||[];
}
function toolName(span){return span.attributes['gen_ai.tool.name']||span.attributes['mcp.tool.name']||span.attributes['tool.name'];}
function toolEvidence(span){
  if(span.toolExecution)return `${span.toolExecution==='server'?'MCP server completed':'MCP handler completed (internal span)'} · ${span.otelStatus==='unset'?'OTel status not reported':span.otelStatus==='error'?'OTel error':'OTel OK'}`;
  return span.kind==='client'?'Client attempt · server completion unconfirmed':'Span kind not reported · server completion unconfirmed';
}
function renderMcpServers(spans){
  const servers=new Map(state.runtime?.demoMode==='live-tools'?[['flow-kubernetes-mcp','Kubernetes MCP'],['flow-gitlab-mcp','GitLab MCP']]:[]);
  const completed=spans.filter(s=>toolName(s)&&s.toolExecution).sort((a,b)=>Number(a.endNs)-Number(b.endNs));
  for(const span of completed)if(!servers.has(span.service))servers.set(span.service,span.attributes['flow.tool.system']||span.service);
  $('mcp-servers').replaceChildren(...[...servers].map(([service,label])=>{
    const calls=completed.filter(s=>s.service===service),latest=calls.at(-1);
    const card=el('button',undefined,`mcp-server${latest?' observed':''}${calls.some(s=>(activeOperations.get(`${s.traceId}/${s.spanId}`)||0)>Date.now())?' active':''}${latest?.status==='error'?' error':''}`);
    card.dataset.service=service;
    card.append(el('strong',label),el('span',latest?toolName(latest):'No MCP execution span received'),el('small',latest?`${calls.length} completed tool call${calls.length===1?'':'s'} · ${time(latest.durationMs)}`:'Waiting in this workflow'));
    if(latest){card.dataset.spanKey=`${latest.traceId}/${latest.spanId}`;card.append(el('small',toolEvidence(latest)));card.onclick=()=>{stopReplay();follow=false;selectedId=latest.traceId;filter=null;render();inspect(latest);};}
    else card.disabled=true;
    return card;
  }));
}
function renderOperations(){
  const spans=scopedSpans();
  renderMcpServers(spans);
  const operations=spans.filter(s=>s.attributes['gen_ai.tool.name']||s.attributes['mcp.tool.name']||s.attributes['tool.name']||s.attributes['flow.security.check'])
    .sort((a,b)=>Number(a.startNs)-Number(b.startNs));
  const cards=operations.slice(-40).map(s=>{
    const a=s.attributes,tool=a['gen_ai.tool.name']||a['mcp.tool.name']||a['tool.name']||s.name;
    const card=el('button',undefined,`operation-card ${s.status}${(activeOperations.get(`${s.traceId}/${s.spanId}`)||0)>Date.now()?' active':''}`);
    card.dataset.spanKey=`${s.traceId}/${s.spanId}`;
    card.append(el('strong',a['flow.tool.system']||s.service),el('span',tool),el('small',`${time(s.durationMs)} · ${toolEvidence(s)}${a['flow.simulated']===true?' · Simulated data':''}`));
    if(a['flow.security.decision']||a['flow.security.check']){
      card.append(el('span',`${a['flow.security.subject']||'Identity unknown'} → ${a['flow.security.resource']||'Resource unknown'} · ${a['flow.security.decision']||'Probe'}`),
        el('small',a['flow.security.authority']||'Enforcement source not reported'));
      if(a['flow.security.check'])card.append(el('small',`HTTP ${a['flow.security.observed_status']??'unknown'} / expected ${a['flow.security.expected_status']??'unknown'} · Backend requests ${a['flow.security.backend_delta']??'unknown'}`));
    }
    card.onclick=()=>{if(!state.traces.some(t=>t.traceId===s.traceId))return;stopReplay();follow=false;selectedId=s.traceId;filter=null;render();inspect(s);};return card;
  });
  $('observed-tools').replaceChildren(...(cards.length?cards:[el('p','Waiting for tool or access-probe spans.','empty')]));
}
function pulse(span,trace) {
  const until=Date.now()+2100;activeNodes.set(span.component,until);
  for(const [key,expiry] of activeOperations)if(expiry<Date.now())activeOperations.delete(key);
  activeOperations.set(`${span.traceId}/${span.spanId}`,until);
  for(const e of trace.edges.filter(e=>e.spanIds.includes(span.spanId))){
    activeNodes.set(e.from,until);activeNodes.set(e.to,until);activeEdges.set(`${e.from}-${e.to}`,until);
  }
  drawMap();renderOperations();
}
function renderRuns(){
  $('trace-count').textContent=state.traces.length;
  if(!state.traces.length){$('runs').replaceChildren(el('p','Run the agent to see its first trace here.','empty'));return;}
  const rows=state.traces.map(t=>{
    const b=el('button',undefined,`run${t.traceId===selectedId?' selected':''}`);b.setAttribute('aria-pressed',String(t.traceId===selectedId));
    const top=el('div',undefined,'run-top');top.append(el('span',`Trace ${t.traceId.slice(0,8)}`,'run-title'),el('i',undefined,`run-status ${t.status}`));
    const meta=el('div',undefined,'run-meta');meta.append(el('span',`${t.spanCount} spans · ${time(t.durationMs)}`),el('span',new Date(Number(t.startNs)/1e6).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})));
    b.append(top,meta);b.onclick=()=>{stopReplay();follow=false;filter=null;selectedId=t.traceId;render();};return b;
  });$('runs').replaceChildren(...rows);
}
function costOf(t){
  if(state.runtime?.demoMode==='fixture')return {value:null,label:'Fixture model. Usage is synthetic or omitted; no billed model cost.'};
  if(manualPrices&&t.inputTokens!==null&&t.outputTokens!==null)return {value:(t.inputTokens*manualPrices.input+t.outputTokens*manualPrices.output)/1e6,label:`${t.usageComplete?'Estimated':'Partial estimate'} from your rates. Full input rate includes cached tokens. Excludes other fees.`};
  return {value:t.costUsd,label:t.costSource==='unknown'?'No per-request USD charge or configured rate.':`${t.costSource==='reported'?'Reported by telemetry':t.costSource==='partial'?'Partial cost; some calls have no price':'Estimated from configured rates'}.`};
}
function render(){
  renderRuns();drawMap();renderOperations();const t=selected();$('follow').disabled=follow;$('replay').disabled=!t||replaying;
  const activity=state.sessionActivity;$('actor-activity').hidden=!activity;
  if(activity){$('actor-states').replaceChildren(...activity.states.map(event=>{const b=el('button',event.state);b.title=`${new Date(Number(event.timestampNs)/1e6).toLocaleTimeString()} · ${event.traceId}`;b.disabled=!state.traces.some(trace=>trace.traceId===event.traceId);b.onclick=()=>{stopReplay();follow=false;filter=null;selectedId=event.traceId;render();};return b;}));}
  if(!t){
    $('graph-caption').textContent=selectedId?`Waiting for trace ${selectedId.slice(0,8)} to arrive.`:'Waiting for the first OTel trace.';
    $('trace-id').textContent=selectedId||'Select a received trace to inspect its spans.';
    $('duration').textContent='—';$('spans').textContent='—';$('tokens').textContent='Not reported';$('cost').textContent='Not reported';$('cost-source').textContent='No price has been assumed.';
    $('timeline').replaceChildren(el('p','Waiting for exported spans for this request.','empty'));
    $('inspection').replaceChildren(el('p','Select a span or a component on the map.','empty'));
    $('internal-spans').disabled=true;
    return;
  }
  $('graph-caption').textContent=`Trace ${t.traceId.slice(0,8)} · recent activity from completed spans`;
  $('trace-id').textContent=t.traceId;$('duration').textContent=time(t.durationMs);$('spans').textContent=t.spanCount;
  $('tokens').textContent=t.inputTokens===null&&t.outputTokens===null?'Not reported':`${count(t.inputTokens)} / ${count(t.outputTokens)}${t.usageComplete?'':' (partial)'}`;
  const cost=costOf(t);$('cost').textContent=money(cost.value);$('cost-source').textContent=cost.label;renderTimeline();
}
function renderTimeline(){
  const t=selected();if(!t)return;$('timeline-title').textContent=filter?`${layout[filter]?.label||filter} spans`:showInternal?'All spans':'Workflow timeline';$('clear-filter').hidden=!filter;
  $('internal-spans').disabled=false;$('internal-spans').textContent=showInternal?'Show workflow spans':`All ${t.spanCount} spans`;
  const callIds=new Set(t.modelCalls.map(c=>c.spanId));
  const spans=t.spans.filter(s=>filter?(s.component===filter||t.edges.some(e=>e.spanIds.includes(s.spanId)&&(e.from===filter||e.to===filter))):(showInternal||s.component==='client'||callIds.has(s.spanId)||s.attributes['gen_ai.tool.name']||s.attributes['mcp.tool.name']||s.attributes['tool.name']||s.attributes['flow.security.check']||s.name.startsWith('invoke_agent ')||['substrate','worker','actor'].includes(s.component)));
  const rows=spans.map(s=>{
    const b=el('button',undefined,`span-row ${s.status}`),track=el('span',undefined,'bar-track'),bar=el('span',undefined,'bar');
    bar.style.left=`${Math.max(0,(Number(s.startNs)-Number(t.startNs))/1e6/Math.max(1,t.durationMs)*100)}%`;
    bar.style.width=`${Math.max(.4,s.durationMs/Math.max(1,t.durationMs)*100)}%`;track.append(bar);
    const name=el('span',s.name,'span-name');name.title=`${s.service} · ${s.name}`;b.append(name,track,el('span',time(s.durationMs),'span-time'));b.onclick=()=>inspect(s);return b;
  });$('timeline').replaceChildren(...(rows.length?rows:[el('p','No spans for this component in the selected trace.','empty')]));
}
function inspect(span){
  const pairs=[['Operation',span.name],['Service',span.service],['Status',span.status],['Span kind',span.kind||'unspecified'],['OTel status',span.otelStatus||'unset'],['Duration',time(span.durationMs)],['Span ID',span.spanId],['Parent ID',span.parentSpanId||'Root or not exported'],...Object.entries(span.attributes)];
  $('inspection').replaceChildren(...pairs.map(([k,v])=>{const row=el('div',undefined,'kv');row.append(el('span',k),el('span',String(v)));return row;}));
}
function stopReplay(){for(const timer of replayTimers)clearTimeout(timer);replayTimers=[];replaying=false;activeNodes.clear();activeEdges.clear();$('mode').textContent='LIVE';$('mode').className='mode';}
$('prompt-form').onsubmit=async event=>{
  event.preventDefault();
  if(submitting||$('invoke').disabled)return;
  const prompt=$('prompt').value.trim();
  if(!prompt||prompt.length>4000){$('notice').textContent='Enter a prompt of up to 4,000 characters.';$('notice').className='notice error';$('prompt').focus();return;}
  submitting=true;stopReplay();$('invoke').disabled=true;$('invoke-label').textContent='Running…';$('notice').className='notice';$('notice').textContent='Sending your prompt. The flow will update as spans arrive.';
  try{
    const response=await fetch('/api/invoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt})});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Could not start the agent call.');
    pendingTraceId=result.traceId;selectedId=result.traceId;follow=false;filter=null;setView('visual');render();
    $('agent-response').hidden=false;$('response-text').textContent='Waiting for the agent response…';$('response-trace').textContent=`Trace ${result.traceId}`;
  }catch(error){$('notice').textContent=error.message;$('notice').className='notice error';$('invoke').disabled=false;$('invoke-label').textContent='Send to agent';}
  finally{submitting=false;}
};
$('prompt').oninput=()=>{$('prompt-count').textContent=`${$('prompt').value.length.toLocaleString()} / 4,000`;};
$('prompt').oninput();
$('prompt').onkeydown=event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();if(!$('invoke').disabled)$('prompt-form').requestSubmit();}};
$('replay').onclick=()=>{
  const t=selected();if(!t)return;stopReplay();follow=false;replaying=true;$('mode').textContent='REPLAY';$('mode').className='mode replay';$('replay').disabled=true;
  const scale=Math.min(1,9000/Math.max(1,t.durationMs));
  for(const s of t.spans)replayTimers.push(setTimeout(()=>pulse(s,t),Math.max(0,(Number(s.endNs)-Number(t.startNs))/1e6*scale)));
  replayTimers.push(setTimeout(()=>{stopReplay();render();},t.durationMs*scale+2400));
};
$('follow').onclick=()=>{stopReplay();follow=true;filter=null;selectedId=state.traces[0]?.traceId||null;render();};
$('clear-filter').onclick=()=>{filter=null;renderTimeline();drawMap();};
$('internal-spans').onclick=()=>{showInternal=!showInternal;filter=null;renderTimeline();drawMap();};
$('pricing').onsubmit=e=>{
  e.preventDefault();const input=Number($('input-rate').value),output=Number($('output-rate').value);
  if($('input-rate').value===''||$('output-rate').value===''||!Number.isFinite(input)||!Number.isFinite(output)||input<0||output<0){$('pricing-status').textContent='Enter both non-negative rates.';return;}
  manualPrices={input,output};$('pricing-status').textContent='Your estimate is active for this browser session. It is not a billed charge.';render();
};
$('reset-pricing').onclick=()=>{manualPrices=null;$('pricing').reset();$('pricing-status').textContent='Rates cleared.';render();};
async function poll(){
  try{
    const r=await fetch('/api/state');if(!r.ok)throw Error('Receiver unavailable');const next=await r.json();
    const fresh=[];for(const t of next.traces)for(const s of t.spans){const key=`${s.traceId}/${s.spanId}`;if(!seen.has(key)&&!initial)fresh.push([s,t]);}
    seen=new Set(next.traces.flatMap(t=>t.spans.map(s=>`${s.traceId}/${s.spanId}`)));state=next;
    if(state.runtime){$('runtime-label').textContent=state.runtime.label;$('prompt-help').textContent=state.runtime.promptHelp;$('demo-mode').hidden=!state.runtime.demoMode;$('demo-mode').textContent=runtimeModes[state.runtime.demoMode]||'Runtime data mode not specified.';$('workflow').closest('label').hidden=state.runtime.demoMode==='connected';$('workflow').disabled=state.runtime.demoMode==='connected';
      if(state.runtime.demoMode==='live-tools'&&$('workflow').dataset.mode!=='live-tools'){
        $('workflow').replaceChildren(...[{id:'custom',label:'Custom prompt'},...(state.runtime.scenarios||[])].map(s=>{const option=el('option',s.label);option.value=s.id;return option;}));
        $('workflow').dataset.mode='live-tools';$('workflow').value='live-combined';
      }if(state.runtime.demoMode==='live-tools'){$('prompt-help').textContent='Live read-only Kubernetes and GitLab tools · Each prompt creates a new session.';if(initial&&state.runtime.demoPrompt){$('prompt').value=state.runtime.demoPrompt;$('prompt').oninput();}}}
    if(follow&&state.traces.length)selectedId=state.traces[0].traceId;
    $('connection').textContent='Receiver connected';$('connection-dot').className='online';
    const inv=state.invocation,waitingForAcceptedTrace=!!pendingTraceId&&inv.traceId!==pendingTraceId,busy=submitting||waitingForAcceptedTrace||['starting','running'].includes(inv.status);$('invoke').disabled=busy;$('invoke-label').textContent=busy?'Running…':'Send to agent';
    if(initial&&inv.traceId){selectedId=inv.traceId;follow=false;}
    if(inv.traceId&&!waitingForAcceptedTrace){pendingTraceId=null;$('agent-response').hidden=false;$('response-trace').textContent=`Trace ${inv.traceId}${inv.sessionId?' · Session '+inv.sessionId:''}`;$('response-text').textContent=busy?'Waiting for the agent response…':inv.text||'Waiting for completion…';}
    if(busy){$('notice').textContent='Calling the agent. Waiting for runtime spans.';$('notice').className='notice';}
    else if(inv.status==='completed'){$('notice').textContent='Agent completed. Inspect the visual flow or switch to Logs.';$('notice').className='notice';}
    else if(inv.status==='failed'){$('notice').textContent=inv.text;$('notice').className='notice error';}
    const revisionKey=`${state.revision}/${state.sessionActivity?.states.length||0}/${inv.status}`;
    if(revisionKey!==lastRevision){lastRevision=revisionKey;render();}
    if(sessionGraph())$('graph-caption').textContent=`${state.sessionActivity.actorName} · ${state.sessionActivity.traceIds.length} related native traces. Details below show the selected trace.`;
    if(!replaying)for(const [s,t] of fresh)if(t.traceId===selectedId||sessionGraph()?.traceIds.includes(t.traceId))pulse(s,t);
    if(inv.exportStatus==='failed'){$('notice').textContent+=' Caller span export failed; inspect the collector.';}
    initial=false;
  }catch(e){$('connection').textContent='Receiver disconnected';$('connection-dot').className='offline';$('notice').textContent='Cannot reach the receiver. Check the local port-forward; reconnecting automatically.';$('notice').className='notice error';}
  setTimeout(poll,600);
}
function renderLogs(){
  if(!logData)return;
  const serviceMenu=$('log-service'),services=logData.services||[];
  const serviceKey=JSON.stringify(services);
  if(serviceMenu.dataset.services!==serviceKey){
    const current=serviceMenu.value;serviceMenu.replaceChildren(...['',...services].map(name=>{const option=el('option',name||'All services');option.value=name;return option;}));
    serviceMenu.value=services.includes(current)?current:'';serviceMenu.dataset.services=serviceKey;
  }
  const minimum=Number($('log-severity').value),records=logData.logs.filter(r=>r.severityNumber>=minimum);
  $('logs-status').textContent=`${logsPaused?'Paused':'Live'} · ${records.length} shown · ${logData.matching} matching · ${logData.retained} retained`;
  const rows=records.map(record=>{
    const row=el('tr');row.append(el('td',Number(record.timestampNs)?new Date(Number(record.timestampNs)/1e6).toLocaleTimeString([], {hour12:false}):'No timestamp'),el('td',record.severity,`severity ${record.severity.toLowerCase()}`),el('td',record.service));
    const actorState=record.attributes?.['ate.actor.state'];
    const message=el('td'),event=el('button',actorState?`${record.event} · ${actorState}`:record.message,'log-event');event.onclick=()=>{$('log-json').textContent=JSON.stringify(record,null,2);$('log-detail').open=true;};message.append(event);row.append(message);
    const trace=el('td');if(record.traceId){const button=el('button',record.traceId.slice(0,10),'log-trace');button.title=record.traceId;button.onclick=()=>{if(state.traces.some(t=>t.traceId===record.traceId)){stopReplay();follow=false;selectedId=record.traceId;filter=null;setView('visual',true);render();}else{$('logs-status').textContent='The trace for this log is no longer retained.';}};trace.append(button);}else trace.textContent='Uncorrelated';row.append(trace);return row;
  });
  if(!rows.length){const row=el('tr'),cell=el('td',logsPaused?'Log view paused. Resume to see new records.':'No matching OTel logs yet. Run the agent to generate model and gateway events.');cell.colSpan=5;row.append(cell);rows.push(row);}
  $('log-rows').replaceChildren(...rows);
}
$('pause-logs').onclick=()=>{logsPaused=!logsPaused;$('pause-logs').textContent=logsPaused?'Resume logs':'Pause logs';renderLogs();};
$('log-severity').onchange=renderLogs;
$('log-scope').onchange=()=>{logData=null;lastLogKey='';};
$('log-service').onchange=()=>{logData=null;lastLogKey='';};
let lastLogKey='';
async function pollLogs(){
  if(!logsPaused){
    try{
      const trace=$('log-scope').value==='selected'?selectedId:null;
      if($('log-scope').value==='selected'&&!trace){$('logs-status').textContent='Select a trace to filter its logs.';}
      else{const service=$('log-service').value||'',params=[];if(trace)params.push('traceId='+encodeURIComponent(trace));if(service)params.push('service='+encodeURIComponent(service));const response=await fetch('/api/logs'+(params.length?'?'+params.join('&'):''));if(!response.ok)throw Error('Logs unavailable');const data=await response.json();const key=`${data.revision}/${trace||'all'}/${service}`;if(key!==lastLogKey){logData=data;lastLogKey=key;renderLogs();}}
    }catch(e){$('logs-status').textContent='Log receiver disconnected. Reconnecting automatically.';}
  }
  setTimeout(pollLogs,800);
}
buildMap();setView(location.hash.slice(1));render();poll();pollLogs();setInterval(()=>drawMap(),700);
