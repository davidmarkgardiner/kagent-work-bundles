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
  skills: {x:815,y:245,label:'Skills and knowledge',labelSize:12,sub:'Native skill operations',icon:'M12 15h13v25H12zM25 15h13v25H25zM17 21h4m8 0h4m-16 6h4m8 0h4'},
  substrate: {x:285,y:385,label:'Agent Substrate',sub:'No local runtime',icon:'M13 20l13-7 13 7-13 7zM13 27l13 7 13-7m-26 7 13 7 13-7'},
  worker: {x:550,y:385,label:'Worker pool',sub:'No runtime telemetry',icon:'M13 16h27v8H13zm0 15h27v8H13zM18 20h1m-1 15h1'},
  actor: {x:815,y:385,label:'Sandbox actor',sub:'No runtime telemetry',icon:'M15 21l12-8 12 8v16H15zM22 37V26h10v11'},
};
const expectedEdges = [['client','kagent'],['kagent','agentgateway'],['agentgateway','model'],['kagent','mcp'],['kagent','skills'],['kagent','substrate'],['substrate','worker'],['worker','actor']];
let state = {traces:[]}, selectedId = null, filter = null, follow = true, initial = true;
let seen = new Set(), activeNodes = new Map(), activeEdges = new Map(), replayTimers = [], replaying = false;
let manualPrices = null, lastRevision = -1;
const activeOperations=new Map();
let showInternal = false;
let logsPaused = false, logData = null;
let currentView = 'visual';
let submitting = false, pendingTraceId = null;
const views = {visual: {panel:'visual-view', description:'Follow the observed request path and inspect its spans.'},onboarding: {panel:'onboarding-view', description:'Follow actual agent calls, then inspect delivery readiness and the independent GoldenScenario receipt.'},logs: {panel:'logs-view', description:'Inspect API calls, status codes, and GenAI events. Select a trace ID to open its visual flow.'}};
function setView(view, focus=false){
  if(!Object.hasOwn(views,view))view='visual';
  for(const [id,config] of Object.entries(views)){
    $(config.panel).hidden=id!==view;
    $(`tab-${id}`).setAttribute('aria-selected',String(id===view));
    $(`tab-${id}`).tabIndex=id===view?0:-1;
  }
  currentView=view;
  $(view==='onboarding'?'onboarding-flow-slot':'visual-flow-slot').append($('runtime-flow'));
  if(view==='onboarding'&&follow){stopReplay();filter=null;selectedId=preferredTraceId()||null;}
  $('view-description').textContent=views[view].description;
  $('prompt-column').hidden=view==='onboarding';$('prompt-column').style.display=view==='onboarding'?'none':'';
  $('demo-intro').hidden=view==='onboarding';$('demo-intro').style.display=view==='onboarding'?'none':'';
  $('agent-workspace').classList.toggle('onboarding-wide',view==='onboarding');
  render();
  history.replaceState(null,'',`#${view}`);
  if(view==='logs'){stopReplay();render();}
  if(focus)$(`tab-${view}`).focus();
}
for(const id of Object.keys(views)){
  $(`tab-${id}`).onclick=()=>setView(id);
  $(`tab-${id}`).onkeydown=event=>{
    const order=['visual','logs','onboarding'],at=order.indexOf(id);
    const keys={ArrowLeft:order[(at+2)%3],ArrowRight:order[(at+1)%3],Home:'visual',End:'onboarding'};
    if(keys[event.key]){event.preventDefault();setView(keys[event.key],true);}
  };
}
function el(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; }
function svgel(tag, attrs) {const e = document.createElementNS(svgNS,tag);for (const [key,value] of Object.entries(attrs))e.setAttribute(key,value);return e;}
function selected() { return state.traces.find(t=>t.traceId===selectedId); }
function readOnlyViewer(){return state.runtime?.readOnlyViewer===true;}
function preferredTraceId(){if(currentView==='onboarding')return onboardingTrace()?.traceId;return readOnlyViewer()?(state.traces.find(t=>t.nativeRequest)?.traceId||state.traces[0]?.traceId):state.invocation?.traceId||state.traces[0]?.traceId;}
function requestActivity(){return state.nativeActivities?.[selectedId]||(selectedId===state.invocation?.traceId?state.sessionActivity:null);}
function selectedActivity(){return requestActivity()||(state.sessionActivity?.traceIds.includes(selectedId)?state.sessionActivity:null);}
function sessionGraph(){return replaying?null:requestActivity();}
$('session-flow').onclick=()=>{const activity=selectedActivity();if(!activity)return;stopReplay();follow=false;filter=null;selectedId=activity.requestTraceId||state.invocation?.traceId;render();};
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
    const title=svgel('text',{class:'label',x:52,y:33});if(n.labelSize)title.setAttribute('style',`font-size:${n.labelSize}px`);title.textContent=n.label;g.append(title);
    const sub=svgel('text',{class:'sub',x:52,y:52,id:`sub-${id}`});sub.textContent=n.sub;g.append(sub);
    const choose=()=>{filter=id;renderTimeline();drawMap();};g.addEventListener('click',choose);g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});$('nodes').append(g);
  }
}
function executionMode(){return selected()?.executionMode||(selectedId===state.invocation?.traceId?state.invocation.executionMode:null)||(state.runtime?.ordinaryObservationOnly?'ordinary':null);}
function renderExecutionPicker(){
  const targets=state.runtime?.executionTargets||[],picker=$('execution-runtime'),key=JSON.stringify(targets);
  if(picker.dataset.targets!==key){const previous=picker.value;picker.replaceChildren(...targets.map(t=>{const option=el('option',t.label);option.value=t.id;return option;}));picker.value=targets.some(t=>t.id===previous)?previous:targets[0]?.id||'';picker.dataset.targets=key;}
  const target=targets.find(t=>t.id===picker.value);
  $('execution-help').textContent=['standalone','ordinary'].includes(target?.mode)?'Native kagent ADK Deployment. No Substrate, worker, or actor is used. Sessions are in memory.':target?.mode==='substrate'?'kagent session in a Substrate actor. Observe worker restore, execution, checkpoint, and suspend.':'Use the configured agent route.';
  picker.disabled=readOnlyViewer()||submitting||['starting','running'].includes(state.invocation?.status);
}
$('execution-runtime').onchange=renderExecutionPicker;
function drawMap() {
  const t=sessionGraph()||selected();const nodes=new Set(t?.components||[]), observed=new Map((t?.edges||[]).map(e=>[`${e.from}-${e.to}`,e]));
  $('graph-scope').textContent=receiptBackendSpans().length?'Selected request + receipt-correlated backend':sessionGraph()?'Observed in this session':'Observed in selected trace';
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
  const activeMcpServices=new Set(scopedSpans().filter(s=>mcpExecution(s)&&(activeOperations.get(`${s.traceId}/${s.spanId}`)||0)>now).map(s=>s.service));
  for(const card of document.querySelectorAll('.operation-card, .mcp-server'))card.classList.toggle('active',card.dataset.service?activeMcpServices.has(card.dataset.service):(activeOperations.get(card.dataset.spanKey)||0)>now);
  const mode=executionMode(),hasSubstrate=t?.components?.some(c=>['substrate','worker','actor'].includes(c));
  $('execution-caption').textContent=['standalone','ordinary'].includes(mode)?'Without Substrate · native kagent ADK Deployment':mode==='substrate'?'With Substrate · session actor':'';
  $('substrate-note').textContent=['standalone','ordinary'].includes(mode)?(hasSubstrate?'Unexpected Substrate activity received for this standalone run. Inspect its spans.':'Not used for this run. The agent is a normal Deployment; worker and actor lanes stay inactive.'):hasSubstrate?(sessionGraph()?'Native runtime spans linked by observed actor identity. Trace details and token counts below stay scoped to the selected trace.':'Native runtime spans received in this trace. Related lifecycle requires shared actor identity.'):state.runtime?.substrateInstalled?'Substrate path configured. Waiting for native runtime spans.':'Substrate path is not configured. Its worker and actor lane stays inactive.';
  $('mcp-explanation').textContent=currentView==='onboarding'&&state.onboarding?.profile?.mcpCapabilityCount===1?'Sampled profile: 0 ToolGrants; 1 fixed profile capability. Client spans show attempts; backend spans report actual handler execution.':currentView==='onboarding'&&state.onboarding?.profile?.toolGrants===0?'Sampled profile: 0 tool grants. No MCP tools attached. MCP stays inactive unless execution spans are received. Native skill / knowledge calls use the separate executor.':'MCP server spans provide execution evidence. Client spans show attempts. Native skill activity appears separately below.';
  if(currentView==='onboarding'&&!nodes.has('mcp')&&state.onboarding?.profile?.toolGrants===0&&!state.onboarding?.profile?.mcpCapabilityCount)$('sub-mcp').textContent='No tools attached · 0 grants';
  if(['standalone','ordinary'].includes(mode)&&!hasSubstrate)for(const id of ['substrate','worker','actor'])$('sub-'+id).textContent='Not used for this run';
  else if(state.runtime?.substrateInstalled&&!nodes.has('substrate'))$('sub-substrate').textContent='Waiting in this trace';
}
function scopedSpans(){
  const scope=sessionGraph();
  const spans=scope?state.traces.filter(t=>scope.traceIds.includes(t.traceId)).flatMap(t=>t.spans):selected()?.spans||[];
  return [...spans,...receiptBackendSpans().filter(extra=>!spans.some(s=>s.traceId===extra.traceId&&s.spanId===extra.spanId))];
}
function receiptBackendSpans(){
  const record=state.onboarding?.golden,trace=selected();
  if(record?.schemaVersion!==2||!record.appliesToCurrent||!trace)return [];
  const proof=record.observations?.find(o=>o.category==='mcp');
  if(!proof||!trace.spans.some(s=>recordedNativeSpan(s,record)&&s.attributes['gen_ai.tool.call.id']===proof.callId))return [];
  const matches=state.traces.flatMap(t=>t.spans).filter(s=>s.kind==='server'&&s.attributes['flow.evidence.source']==='mcp-handler'&&s.attributes['flow.execution.id']===proof.executionId&&s.attributes['mcp.tool.name']===proof.toolName);
  return matches.length===1?matches:[];
}
function toolName(span){return span.attributes['gen_ai.tool.name']||span.attributes['mcp.tool.name']||span.attributes['tool.name'];}
function mcpExecution(span){return ['server','kagent-tools-internal'].includes(span.toolExecution)&&!['skill','native'].includes(span.toolCategory);}
function toolEvidence(span){
  const status=span.otelStatus==='unset'||!span.otelStatus?'OTel status not reported':span.otelStatus==='error'?'OTel error':'OTel OK';
  const record=state.onboarding?.golden;
  const observation=record?.schemaVersion===2&&record.appliesToCurrent&&recordedNativeSpan(span,record)?record.observations.find(o=>o.callId===span.attributes['gen_ai.tool.call.id']):null;
  const label=observation?.category==='knowledge'?'Knowledge read · runner-correlated':observation?.category==='skill'?'Skill read · runner-correlated':span.toolCategory==='skill'?'Native ADK skill execution':'Native runtime tool execution';
  if(['skill','native'].includes(span.toolCategory))return `${label} · ${span.attributes['kagent.runtime']||(state.runtime?.ordinaryObservationOnly?'ADK Python SDK resource with reviewed identity':'Runtime not reported')} · ${span.toolExecution?'Span ended':'Execution provenance not reported'} · ${status}`;
  if(mcpExecution(span))return `${span.attributes['flow.evidence.source']==='mcp-handler'?'Backend-observed completion · independent trace':span.toolExecution==='server'?'MCP server completed':'MCP handler completed (internal span)'} · ${status}`;
  if(span.toolCategory==='mcp'&&['MCPTool','McpTool'].includes(span.attributes['gen_ai.tool.type']))return `SDK MCP attempt · backend completion unconfirmed · ${status}`;
  return span.kind==='client'?'Client attempt · server completion unconfirmed':'Span kind not reported · server completion unconfirmed';
}
function renderMcpServers(spans){
  const servers=new Map(state.runtime?.demoMode==='live-tools'?[['flow-kubernetes-mcp','Kubernetes MCP'],['flow-gitlab-mcp','GitLab MCP']]:[]);
  const completed=spans.filter(s=>toolName(s)&&mcpExecution(s)).sort((a,b)=>Number(a.endNs)-Number(b.endNs));
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
  const operations=spans.filter(s=>toolName(s)!=='(merged tools)'&&(toolName(s)||s.attributes['flow.security.check']))
    .sort((a,b)=>Number(a.startNs)-Number(b.startNs));
  const cardFor=s=>{
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
  };
  const recent=operations.slice(-40),skills=recent.filter(s=>s.toolCategory==='skill').map(cardFor),tools=recent.filter(s=>s.toolCategory!=='skill').map(cardFor);
  $('observed-skills').replaceChildren(...(skills.length?skills:[el('p','Waiting for native skill execution spans.','empty')]));
  $('observed-tools').replaceChildren(...(tools.length?tools:[el('p','Waiting for tool or access-probe spans.','empty')]));
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
  if(!state.traces.length){$('runs').replaceChildren(el('p',readOnlyViewer()?'Waiting for externally exported traces.':'Run the agent to see its first trace here.','empty'));return;}
  const traces=readOnlyViewer()?[...state.traces.filter(t=>t.nativeRequest),...state.traces.filter(t=>!t.nativeRequest)]:[...state.traces.filter(t=>t.executionMode),...state.traces.filter(t=>!t.executionMode)];
  const rows=traces.map(t=>{
    const b=el('button',undefined,`run${t.traceId===selectedId?' selected':''}`);b.setAttribute('aria-pressed',String(t.traceId===selectedId));
    const top=el('div',undefined,'run-top'),status=el('i',undefined,`run-status ${t.status}`);if((t.nativeRuntimeIdentity||t.status==='unknown')&&t.status!=='error'){status.style.background='var(--muted)';status.title='Observed native spans; task completion is not inferred.';}top.append(el('span',`${t.executionMode==='standalone'?'Without Substrate · ':t.executionMode==='substrate'?'With Substrate · ':readOnlyViewer()&&t.nativeRuntimeIdentity?`${t.nativeRuntimeIdentity.agentName||t.nativeRuntimeIdentity.runtime} · `:''}Trace ${t.traceId.slice(0,8)}`,'run-title'),status);
    const meta=el('div',undefined,'run-meta');meta.append(el('span',`${t.spanCount} spans · ${time(t.durationMs)}`),el('span',new Date(Number(t.startNs)/1e6).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})));
    b.append(top,meta);b.onclick=()=>{stopReplay();follow=false;filter=null;selectedId=t.traceId;render();};return b;
  });$('runs').replaceChildren(...rows);
}
function costOf(t){
  if(state.runtime?.demoMode==='fixture')return {value:null,label:'Fixture model. Usage is synthetic or omitted; no billed model cost.'};
  if(t.modelUsageSource==='native-runtime')return {value:t.costUsd,label:`Native runtime reports. ${t.costSource==='reported'?'Reported per-request USD charge.':t.costSource==='partial'?'Partial reported cost; other model reports are excluded or have no charge.':'Per-request USD charge not reported.'}`};
  if(manualPrices&&t.inputTokens!==null&&t.outputTokens!==null)return {value:(t.inputTokens*manualPrices.input+t.outputTokens*manualPrices.output)/1e6,label:`${t.usageComplete?'Estimated':'Partial estimate'} from your rates. Full input rate includes cached tokens. Excludes other fees.`};
  return {value:t.costUsd,label:t.costSource==='unknown'?'No per-request USD charge or configured rate.':`${t.costSource==='reported'?'Reported by telemetry':t.costSource==='partial'?'Partial cost; some calls have no price':'Estimated from configured rates'}.`};
}
function render(){
  renderOnboarding();
  renderRuns();drawMap();renderOperations();const t=selected();$('follow').disabled=follow;$('replay').disabled=!t||replaying;
  const activity=selectedActivity();$('actor-activity').hidden=!activity;
  if(activity){$('actor-states').replaceChildren(...activity.states.map(event=>{const b=el('button',event.state);b.title=`${new Date(Number(event.timestampNs)/1e6).toLocaleTimeString()} · ${event.traceId}`;b.disabled=!state.traces.some(trace=>trace.traceId===event.traceId);b.onclick=()=>{stopReplay();follow=false;filter=null;selectedId=event.traceId;render();};return b;}));}
  if(!t){
    $('graph-caption').textContent=selectedId?`Waiting for trace ${selectedId.slice(0,8)} to arrive.`:'Waiting for the first OTel trace.';
    $('trace-id').textContent=selectedId||'Select a received trace to inspect its spans.';
    $('duration').textContent='—';$('spans').textContent='—';$('tokens').textContent='Not reported';$('cost').textContent='Not reported';$('cost-source').textContent='No price has been assumed.';
    $('model-usage-source').textContent='No model reports received.';
    $('timeline').replaceChildren(el('p','Waiting for exported spans for this request.','empty'));
    $('inspection').replaceChildren(el('p','Select a span or a component on the map.','empty'));
    $('internal-spans').disabled=true;
    return;
  }
  $('graph-caption').textContent=`Trace ${t.traceId.slice(0,8)} · recent activity from completed spans`;
  $('trace-id').textContent=t.traceId;$('duration').textContent=time(t.durationMs);$('spans').textContent=t.spanCount;
  $('tokens').textContent=t.inputTokens===null&&t.outputTokens===null?'Not reported':`${count(t.inputTokens)} / ${count(t.outputTokens)}${t.usageComplete?'':' (partial)'}`;
  $('model-usage-source').textContent=t.modelUsageSource==='native-runtime'?'Native runtime reports':t.modelUsageSource==='reconciled-reports'?'Runtime / gateway reports':'No model reports received.';
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
  if(readOnlyViewer()||submitting||$('invoke').disabled)return;
  const prompt=$('prompt').value.trim();
  if(!prompt||prompt.length>4000){$('notice').textContent='Enter a prompt of up to 4,000 characters.';$('notice').className='notice error';$('prompt').focus();return;}
  submitting=true;stopReplay();$('execution-runtime').disabled=true;$('invoke').disabled=true;$('invoke-label').textContent='Running…';$('notice').className='notice';$('notice').textContent='Sending your prompt. The flow will update as spans arrive.';
  try{
    const response=await fetch('/api/invoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,runtime:$('execution-runtime').value})});
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
$('follow').onclick=()=>{stopReplay();follow=true;filter=null;selectedId=preferredTraceId()||null;render();};
$('clear-filter').onclick=()=>{filter=null;renderTimeline();drawMap();};
$('internal-spans').onclick=()=>{showInternal=!showInternal;filter=null;renderTimeline();drawMap();};
$('pricing').onsubmit=e=>{
  if(selected()?.modelUsageSource==='native-runtime'){e.preventDefault();$('pricing-status').textContent='Native runtime reports use reported charges only.';return;}
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
    const viewer=readOnlyViewer();$('invocation-controls').hidden=viewer;$('invocation-controls').style.display=viewer?'none':'';$('prompt').disabled=viewer;$('intro-description').textContent=viewer?'Follow native requests as their runtime exports metadata.':'Send a prompt, then follow the components it actually touches.';
    renderExecutionPicker();
    if(state.runtime){$('runtime-label').textContent=state.runtime.label;$('prompt-help').textContent=state.runtime.promptHelp;$('demo-mode').hidden=!state.runtime.demoMode;$('demo-mode').textContent=runtimeModes[state.runtime.demoMode]||'Runtime data mode not specified.';$('workflow').closest('label').hidden=state.runtime.demoMode==='connected';$('workflow').disabled=viewer||state.runtime.demoMode==='connected';
      if(state.runtime.demoMode==='live-tools'&&$('workflow').dataset.mode!=='live-tools'){
        $('workflow').replaceChildren(...[{id:'custom',label:'Custom prompt'},...(state.runtime.scenarios||[])].map(s=>{const option=el('option',s.label);option.value=s.id;return option;}));
        $('workflow').dataset.mode='live-tools';$('workflow').value='live-combined';
      }if(state.runtime.demoMode==='live-tools'){$('prompt-help').textContent='Live read-only Kubernetes and GitLab tools · Each prompt creates a new session.';if(initial&&state.runtime.demoPrompt){$('prompt').value=state.runtime.demoPrompt;$('prompt').oninput();}}}
    if(follow&&(state.traces.length||currentView==='onboarding'))selectedId=preferredTraceId()||null;
    $('connection').textContent='Receiver connected';$('connection-dot').className='online';
    const inv=state.invocation,waitingForAcceptedTrace=!!pendingTraceId&&inv.traceId!==pendingTraceId,busy=submitting||waitingForAcceptedTrace||['starting','running'].includes(inv.status);$('invoke').disabled=viewer||busy;$('invoke-label').textContent=busy?'Running…':'Send to agent';
    if(initial&&inv.traceId&&!viewer&&currentView!=='onboarding'){selectedId=inv.traceId;follow=false;}
    if(viewer)$('agent-response').hidden=true;
    else if(inv.traceId&&!waitingForAcceptedTrace){pendingTraceId=null;$('agent-response').hidden=false;$('response-trace').textContent=`Trace ${inv.traceId}${inv.sessionId?' · Session '+inv.sessionId:''}`;$('response-text').textContent=busy?'Waiting for the agent response…':inv.text||'Waiting for completion…';}
    if(viewer){$('notice').textContent='Read-only viewer · observing external agent calls. Span activity does not establish task completion.';$('notice').className='notice';}
    else if(busy){$('notice').textContent='Calling the agent. Waiting for runtime spans.';$('notice').className='notice';}
    else if(inv.status==='completed'){$('notice').textContent='Agent completed. Inspect the visual flow or switch to Logs.';$('notice').className='notice';}
    else if(inv.status==='failed'){$('notice').textContent=inv.text;$('notice').className='notice error';}
    renderOnboarding();
    const revisionKey=`${state.revision}/${state.sessionActivity?.states.length||0}/${JSON.stringify(state.nativeActivities||{})}/${inv.status}/${selectedId}`;
    if(revisionKey!==lastRevision){lastRevision=revisionKey;render();}
    const graph=sessionGraph();if(graph)$('graph-caption').textContent=`${graph.actorName} · ${graph.traceIds.length} related native traces. Details below show the selected trace.`;
    if(!replaying)for(const [s,t] of fresh)if(t.traceId===selectedId||sessionGraph()?.traceIds.includes(t.traceId))pulse(s,t);
    if(inv.exportStatus==='failed'){$('notice').textContent+=' Caller span export failed; inspect the collector.';}
    initial=false;
  }catch(e){$('connection').textContent='Receiver disconnected';$('connection-dot').className='offline';$('notice').textContent='Cannot reach the receiver. Check the local port-forward; reconnecting automatically.';$('notice').className='notice error';}
  renderOnboarding();
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
const onboardingLabels={declarations:'Git → Flux',hosted:'HostedAgent',profile:'Approved model + harness',skill:'Skill instructions',knowledge:'Knowledge references',tools:'Fixed MCP capability',agent:'Native Agent'};
const onboardingReasons={Current:'Current conditions and reviewed pins',AwaitingConditions:'Waiting for current conditions',StaleGeneration:'Conditions describe an older generation',Deleting:'Resource is being deleted',PinMismatch:'Reviewed content changed',UIDChanged:'Resource identity was replaced',RevisionMismatch:'Desired revision has not succeeded',DeliveryRevisionMismatch:'Flux has not applied the reviewed source commit',BindingMismatch:'Reviewed bindings are not current',ReferenceMismatch:'Native references do not match',ProfileMismatch:'Reviewed profile is not current',DependencyMismatch:'A required dependency is not current',Unavailable:'Observation unavailable',ReadDenied:'Observer cannot read this named object',Missing:'Object has not been observed',TornSample:'Object changed during sampling',InvalidMetadata:'Observation failed validation',NotConfigured:'No observation configured',Expired:'Observation expired'};
function recordedNativeSpan(span,record){
  const a=span.attributes||{};
  if(record.schemaVersion===2)return a['gen_ai.conversation.id']===record.sessionId&&a['gen_ai.task.id']===record.taskId&&span.attributes['service.name']===(record.sdkServiceName||record.agentName)&&span.attributes['service.namespace']===(record.sdkServiceNamespace||record.namespace);
  return a['gen_ai.conversation.id']===record.sessionId&&a['a2a.task.id']===record.taskId&&a['kagent.runtime']==='adk-go'
    &&(a['gen_ai.agent.name']===record.agentName||a['gen_ai.agent.id']===`${record.namespace}/${record.agentName}`||a['gen_ai.main_agent.name']===record.agentName||a['gen_ai.main_agent.id']===`${record.namespace}/${record.agentName}`);
}
function goldenTraces(record){
  if(!record)return [];
  return state.traces.filter(trace=>{
    const identity=trace.nativeRuntimeIdentity;
    return identity&&(identity.agentName===record.agentName||identity.agentId===`${record.namespace}/${record.agentName}`)&&trace.spans.some(span=>recordedNativeSpan(span,record));
  }).sort((a,b)=>a.traceId.localeCompare(b.traceId));
}
function onboardingAgentMatches(trace){
  const view=state.onboarding,identity=trace?.nativeRuntimeIdentity;
  return !!(view?.agentName&&view.namespace&&identity&&(identity.agentName===view.agentName||identity.agentId===`${view.namespace}/${view.agentName}`));
}
function onboardingTrace(){
  const exact=goldenTraces(state.onboarding?.golden);
  if(exact.length)return exact.find(trace=>trace.nativeRequest)||exact[0];
  return state.traces.filter(trace=>trace.nativeRequest&&onboardingAgentMatches(trace)).sort((a,b)=>Number(b.startNs)-Number(a.startNs))[0]||null;
}
function openGoldenTrace(traceId){
  const current=goldenTraces(state.onboarding?.golden).find(trace=>trace.traceId===traceId);
  if(!current)return;
  stopReplay();follow=false;filter=null;selectedId=current.traceId;setView('visual',true);render();
}
function renderOnboarding(now=Date.now()/1000){
  const ordinary=state.runtime?.ordinaryObservationOnly===true;
  $('observed-skills-help').textContent=ordinary?'SDK spans omit arguments. Accepted runner receipts identify reviewed skill and knowledge reads by exact tool-call ID; other calls remain unattributed.':'Skills and knowledge share the native skill executor. Spans omit arguments, so individual calls cannot be attributed to a skill or knowledge package. Select a call to inspect its metadata.';
  $('onboarding-test-title').textContent=ordinary?'Recorded combined acceptance test':'Recorded GoldenScenario test';
  $('onboarding-test-help').textContent=ordinary?'An operator-supplied receipt verifies exact document reads and the independently audited MCP result. Metadata readiness is checked separately.':'A GoldenScenario tests the agent produced by our golden path. This recorded result does not automatically publish an agent.';
  $('onboarding-client-help').textContent=ordinary?'Invoke the ordinary Agent using the bundled A2A JSON-RPC helper through the internal controller. This viewer has no invocation credentials or public agent endpoint.':'Native CLI session create → invoke → session get. A2A over gRPC, namespace/name routing, internal controller port 8083. No public endpoint is provisioned here.';
  const view=state.onboarding, fresh=view?.freshness==='current'&&view.capturedAt<=now&&now<view.expiresAt;
  const badge=$('onboarding-freshness');badge.textContent=fresh?'Current sampled metadata':view?.capturedAt?'Expired observation':'Observation unavailable';badge.className=`onboarding-badge ${fresh?'ready':'unknown'}`;
  $('onboarding-summary').textContent=view?.capturedAt?`${view.namespace}/${view.hostedName} · sampled ${new Date(view.capturedAt*1000).toLocaleString()} · expires ${new Date(view.expiresAt*1000).toLocaleTimeString()}`:'Waiting for the named GET observer. Current readiness is unknown.';
  $('onboarding-pipeline').replaceChildren(...(view?.schemaVersion===2?Object.keys(onboardingLabels):Object.keys(onboardingLabels).filter(key=>key!=='tools')).map(key=>{
    const observed=view?.stages?.find(s=>s.key===key),status=fresh?observed?.state||'unknown':'unknown';
    const card=el('article',undefined,`onboarding-stage ${status}`),name=el('h3',onboardingLabels[key]);
    card.append(el('span',status,'onboarding-badge '+status),name,el('p',fresh?onboardingReasons[observed?.reasonCode]||'Observation unavailable':'Current readiness unknown'));
    const role=key==='profile'?'model':key,pin=view?.pins?.[role];if(pin)card.append(el('small',pin.name));
    if(key==='profile'&&view?.profile)card.append(el('small',`${view.profile.modelName} · ${view.profile.modelProfile} · 0 ToolGrants${view.profile.mcpCapabilityCount===1?'; 1 fixed profile capability':''}`));
    card.append(el('small',fresh?`Kubernetes metadata · ${Math.max(0,Math.floor(now-view.capturedAt))} s ago`:'Kubernetes metadata · unavailable'));
    return card;
  }));
  const record=view?.golden, traces=goldenTraces(record), applicable=fresh&&record?.appliesToCurrent===true&&record.recordedAt<=now;
  const ready=fresh?(view.stages||[]).filter(stage=>stage.state==='ready').length:0;
  $('onboarding-readiness').textContent=fresh?`${ready} / ${view.stages.length} onboarding checks ready · ${view.namespace}/${view.agentName}${view.profile?.toolGrants===0?` · 0 ToolGrants${view.profile?.mcpCapabilityCount===1?'; 1 fixed capability':''}`:''}`:'Current onboarding readiness unknown. Runtime evidence remains available below.';
  const trace=selected(), exact=trace&&traces.some(item=>item.traceId===trace.traceId);
  $('onboarding-flow-scope').textContent=trace?`${follow?'Following':'Manual selection'} · ${exact?'Recorded acceptance session / task':trace.nativeRequest?'Observed request · not an acceptance test':'Observed trace · not an acceptance test'} · trace ${trace.traceId.slice(0,10)} · agent ${trace.nativeRuntimeIdentity?.agentName||trace.nativeRuntimeIdentity?.agentId||'identity not reported'}${onboardingAgentMatches(trace)?'':' (outside configured agent scope)'}. Select a component to inspect its calls.`:'No retained native request for the configured agent. Waiting for observed runtime spans.';

  $('onboarding-golden').replaceChildren(...(record?[el('strong',record.result==='passed'?'Passing runner receipt':'Failed runner receipt','golden-result'),el('p',`${record.scenarioName} · receipt recorded ${new Date(record.recordedAt*1000).toLocaleString()}`),el('p',applicable?'Recorded test matches current dependency pins.':'Historical result; current pins differ or cannot be verified.'),el('small',record.schemaVersion===2?`Agent spec SHA-256 ${record.agentSpecSha256}`:`Revision ${record.agentRevision}`)]:[el('p','No validated operator-supplied runner receipt.')]));
  const counts=record?.schemaVersion===2?{skills:0,read_file:0,get_demo_status:0}:{load_skill:0,load_skill_resource:0},seenReads=new Set();
  for(const trace of traces)for(const span of trace.spans){const a=span.attributes||{},key=`${trace.traceId}/${span.spanId}`;if(!seenReads.has(key)&&recordedNativeSpan(span,record)&&Object.hasOwn(counts,a['gen_ai.tool.name'])){seenReads.add(key);counts[a['gen_ai.tool.name']]++;}}
  $('onboarding-runtime').textContent=traces.length?`${Object.entries(counts).map(([name,count])=>`${count} ${name}`).join(' · ')} spans across ${traces.length} retained traces in the exact recorded session/task. Span activity alone does not establish task completion.`:'No retained native trace matches the recorded session, task, and agent identity. Runtime reads are unknown.';
  const button=$('onboarding-trace');button.disabled=!traces.length;button.textContent=traces.length>1?'View first matching trace':'View recorded test trace';button.onclick=()=>openGoldenTrace(traces[0]?.traceId);
  $('onboarding-other-traces').replaceChildren(...traces.slice(1).map(trace=>{const link=el('button',`View trace ${trace.traceId.slice(0,10)}`);link.onclick=()=>openGoldenTrace(trace.traceId);return link;}));
  $('onboarding-history').replaceChildren(...(view?.history||[]).map(item=>el('p',`${new Date(item.observedAt*1000).toLocaleTimeString()} · ${item.stages.map(s=>`${onboardingLabels[s.key]}: ${s.state}`).join(' · ')}`)));
  $('onboarding-pins').replaceChildren(...Object.entries(view?.pins||{}).map(([role,pin])=>el('p',`${role}: ${pin.kind}/${pin.name} · UID ${pin.uid} · generation ${pin.generation??'n/a'} · body SHA-256 ${pin.bodySha256||pin.specSha256}`)));
  $('onboarding-connection').textContent=view?.agentName?`Tenant ${view.namespace}/${view.agentName} · internal controller http://kagent-controller.kagent.svc.cluster.local:8083`:'Native connection identity is unavailable until an observation is published.';
}
globalThis.onhashchange=()=>setView(location.hash.slice(1));
buildMap();setView(location.hash.slice(1));render();poll();pollLogs();setInterval(()=>drawMap(),700);
