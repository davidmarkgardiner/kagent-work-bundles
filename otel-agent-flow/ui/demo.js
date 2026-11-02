'use strict';
globalThis.createDemoPanel = function ({openTrace}) {
  const get=id=>document.getElementById(id);
  const node=(tag,text,className)=>{const item=document.createElement(tag);if(text!==undefined)item.textContent=text;if(className)item.className=className;return item;};
  const value=input=>input===null||input===undefined||input===''?'Not reported':String(input);
  const approvalTime=input=>typeof input==='number'&&Number.isFinite(input)?new Date(input*1000).toISOString():value(input);
  const percent=input=>typeof input==='number'&&Number.isFinite(input)?`${(input*100).toFixed(1)}%`:'Not reported';
  const phases={ready:'Ready to start',preparing:'Preparing incident',fault_injected:'Fault injected',observing:'Observing fault',classifying:'Model classifying',suppressed:'Dispatch suppressed',dispatching:'Dispatching to kagent',triaging:'kagent investigating',waiting_ci:'Waiting for CI',waiting_review:'Waiting for review',waiting_human:'Waiting for dashboard approval',merging:'Kagent merging approved fix',reconciling:'GitOps restoring application',verifying:'Agent verifying recovery',closing_ticket:'Closing ticket',closed:'Ticket closure reported',blocked:'Blocked',unknown:'Status unknown'};
  const steps=[['fault','Fault and observation',['preparing','fault_injected','observing']],['classification','Model decision',['classifying','suppressed']],['kagent','Native kagent triage',['dispatching','triaging']],['pr','Remedy and merge request',['waiting_ci','waiting_review']],['human','Dashboard approval and agent merge',['waiting_human','merging']],['verification','Recovery verification and ticket',['reconciling','verifying','closing_ticket','closed']]];
  const stages=[
    ['fault','Fault','Inject the isolated lab fault through GitLab and Flux, then observe Kyverno admission failures.'],
    ['classify','Classify','Classify the observed event. Only a critical event above the confidence threshold can reach Kagent.'],
    ['triage','Kagent triage','Kagent investigates the incident using its skills, knowledge and scoped Kubernetes and GitLab tools.'],
    ['review','Remedy + PR','Create a scoped repository fix, run CI and obtain an independent review of the exact commit.'],
    ['approval','Your approval','A human reviews and approves the exact proposed commit in the dashboard.'],
    ['merge','Agent merge','Kagent uses the recorded human approval to merge the reviewed fix through the GitLab tool.'],
    ['recovery','GitOps recovery','Flux applies the merge revision. Wait for the application, then measure valid admission, invalid denial and HTTP recovery.'],
    ['verify','Verify','A separate Kagent task verifies the recovery using current runtime evidence and the scoped verification tool.'],
    ['resolve','Resolved','Close the GitLab issue only after recovery verification, then confirm that the issue is closed.']
  ];
  const componentLabels={client:'Agent client',kagent:'Kagent',substrate:'Agent Substrate',worker:'Worker',actor:'Actor',agentgateway:'Agentgateway',model:'Model',mcp:'MCP tools',skills:'Skills & knowledge'};
  const workflowLabels={passed:'Completed',active:'In progress',waiting:'Waiting',upcoming:'Not started',blocked:'Blocked',unknown:'Unconfirmed',suppressed:'Suppressed'};
  let inspection={runId:null,stageId:null};
  let demo=null,traces=[],connected=false,pending=false,approvalPending=false,approvalAttempt=null,resumePending=false,resumeAttempt=null,message='',lastRender='',display={},lastStage='';
  const safeUrl=input=>{try{const url=new URL(input),allowed=new URL(demo?.gitlabOrigin===undefined?'https://gitlab.com':demo.gitlabOrigin);return allowed.protocol==='https:'&&!allowed.username&&!allowed.password&&allowed.pathname==='/'&&!allowed.search&&!allowed.hash&&url.protocol==='https:'&&url.origin===allowed.origin&&!url.username&&!url.password?url.href:null;}catch{return null;}};
  function link(target,label,url){target.replaceChildren();const href=safeUrl(url);if(href){const anchor=node('a',label);anchor.href=href;anchor.target='_blank';anchor.rel='noopener noreferrer';target.append(anchor);}else target.append(node('span',url?'Link unavailable. Expected the configured HTTPS GitLab origin.':'Not reported'));}
  const hasNonce=()=>typeof demo?.csrf==='string'&&demo.csrf.length>0;
  const approvalKey=()=>`${demo?.runId||''}/${demo?.remedy?.headSha||''}`;
  const approvalHeld=()=>approvalAttempt&&approvalAttempt.runId===demo?.runId&&(['accepted','unknown'].includes(approvalAttempt.state)||(approvalAttempt.key===approvalKey()&&(approvalAttempt.state!=='forbidden'||approvalAttempt.csrf===demo.csrf)));
  const canApprove=()=>demo?.phase==='waiting_human'&&demo.actions?.approve?.enabled===true&&connected&&hasNonce()&&!pending&&!approvalPending&&!resumePending&&!approvalHeld()&&typeof demo.runId==='string'&&demo.runId.length>0&&/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(demo.remedy?.headSha||'')&&demo.remedy?.ci==='passed'&&demo.remedy?.review==='passed';
  const resumeHeld=()=>resumeAttempt&&resumeAttempt.runId===demo?.runId&&['accepted','unknown'].includes(resumeAttempt.state);
  const canResume=()=>demo?.phase==='blocked'&&demo?.actions?.resume?.enabled===true&&connected&&hasNonce()&&!pending&&!approvalPending&&!resumePending&&!resumeHeld()&&demo.running!==true&&typeof demo.runId==='string'&&demo.runId.length>0;
  const responseError=(body,fallback)=>typeof body?.error==='string'?body.error.slice(0,240).replace(/[\x00-\x1f\x7f]/g,' '):fallback;
  function adoptDemo(next,expectedRunId=null){
    if(!next||next.enabled!==true||expectedRunId&&(next.runId!==expectedRunId||demo?.runId!==expectedRunId))return false;
    demo={...next,csrf:typeof next.csrf==='string'?next.csrf:demo?.csrf,gitlabOrigin:next.gitlabOrigin===undefined?demo?.gitlabOrigin:next.gitlabOrigin};return true;
  }
  async function refreshDemo(expectedRunId=null){
    const response=await fetch('/api/state');
    if(response.ok===false)throw Error('Incident state unavailable');
    const body=await response.json();return adoptDemo(body.demo,expectedRunId);
  }
  const retained=id=>!!id&&traces.some(trace=>trace.traceId===id&&Array.isArray(trace.spans)&&trace.spans.length>0);
  function traceButton(id,label='View agent trace'){const button=node('button',label);button.type='button';button.disabled=!retained(id);button.onclick=()=>{if(retained(id))openTrace(id);};return button;}
  function renderStageDetail(flow,stageId){
    const definition=stages.find(([id])=>id===stageId),stage=flow?.stages?.find(item=>item.id===stageId);
    const history=stage?.controllerEvents||[],records=(flow?.observations||[]).filter(record=>record.stageId===stageId);
    const status=stage?.workflow||'unknown',latest=history.at(-1);
    get('demo-stage-title').textContent=`${stages.indexOf(definition)+1}. ${definition[1]}`;
    get('demo-stage-purpose').textContent=definition[2];
    get('demo-stage-status').textContent=workflowLabels[status]||'Unconfirmed';
    get('demo-stage-status').className=`demo-stage-status ${status}`;
    get('demo-stage-mode').textContent=inspection.stageId?'Inspecting this stage. The live workflow continues below.':'Following the current workflow stage.';
    get('demo-stage-follow').hidden=inspection.stageId===null;
    get('demo-stage-follow').onclick=()=>{inspection.stageId=null;render();};
    get('demo-stage-outcome').textContent=latest?.message||(status==='upcoming'?'No operation recorded for this stage yet.':status==='passed'?'The controller reports completion; detailed receipts are unavailable.':'No controller receipt is available for this stage.');
    const facts={
      fault:[['Incident',demo.runId],['Issue',demo.ticket?.iid?`#${demo.ticket.iid}`:null]],
      classify:[['Decision',demo.classifier?.decision],['Severity',demo.classifier?.severity],['Confidence',percent(demo.classifier?.confidence)],['Threshold',percent(demo.classifier?.threshold)]],
      triage:[['Agent',demo.native?.agent],['Task',demo.native?.taskId],['Task state',demo.native?.state]],
      review:[['Fix',demo.remedy?.summary],['Commit',demo.remedy?.headSha],['CI',demo.remedy?.ci],['Independent review',demo.remedy?.review]],
      approval:[['Approval',demo.approval?.state],['Commit',demo.approval?.headSha],['Approved by',demo.approval?.approvedBy],['Recorded at',approvalTime(demo.approval?.approvedAt)]],
      merge:[['Merge',demo.merge?.status],['Merge commit',demo.merge?.sha],['Agent task',demo.merge?.taskId]],
      recovery:[['Expected merge revision',demo.merge?.sha],['Recovery gate',workflowLabels[status]||'Unconfirmed']],
      verify:[['Agent task',demo.verification?.taskId],['Task state',demo.verification?.state],['Evidence digest',demo.verification?.checks?.evidenceDigest]],
      resolve:[['Issue',demo.ticket?.iid?`#${demo.ticket.iid}`:null],['Issue state',demo.ticket?.state],['Closure verified',demo.phase==='closed'&&demo.ticket?.state==='closed'&&demo.ticket?.closedVerified===true?'Yes':'Not verified']]
    };
    get('demo-stage-facts').replaceChildren(...facts[stageId].map(([label,input])=>{const row=node('div');row.append(node('dt',label),node('dd',value(input)));return row;}));
    const components=new Map();
    for(const record of records){
      const label=record.source==='coordinator'?'Demo controller':componentLabels[record.component];
      if(label)components.set(label,(components.get(label)||0)+1);
    }
    get('demo-stage-components').replaceChildren(...(components.size?[...components].map(([label,count])=>node('li',`${label} · ${count}`, 'demo-component-chip')):[node('li','No retained component telemetry for this stage.')]));
    get('demo-stage-coverage').textContent=records.length?`${records.length} retained OTel observations for this stage. Component names come only from those records.`:'No retained OTel for this stage. Its description and controller receipts do not prove which native components executed.';
    get('demo-stage-history-count').textContent=`Controller history (${history.length})`;
    get('demo-stage-history').replaceChildren(...(history.length?history.map(event=>{const item=node('li');item.append(node('time',value(event.time)),node('strong',`${value(event.step)} · ${value(event.state)}`),node('p',value(event.message)));return item;}):[node('li','No retained controller receipts for this stage.')]));
    get('demo-stage-otel-count').textContent=`Received OTel records (${records.length})`;
    const list=get('demo-stage-otel'),previous=new Map(Array.from(list.children).map(item=>[item.dataset.recordKey,item]));
    const items=records.length?records.slice(-30).reverse().map(record=>{
      const spanRetained=traces.some(trace=>trace.traceId===record.traceId&&trace.spans?.some(span=>span.spanId===record.spanId));
      const key=JSON.stringify([demo.runId,stageId,record.id,record.source,record.summary||record.operation,record.traceId,record.spanId,record.scopeBasis,spanRetained]);
      if(previous.has(key))return previous.get(key);
      const item=node('li');item.dataset.recordKey=key;
      item.append(node('strong',record.source==='coordinator'?'Coordinator reported':'OTel observed'),node('p',record.summary||record.operation||'Operation received'));
      if(spanRetained)item.append(traceButton(record.traceId,'Inspect stage trace'));
      else if(record.traceId)item.append(node('small','Matching span is no longer retained.'));
      if(record.scopeBasis==='native-tool-window')item.append(node('small','MCP pairing inferred from the same trace, tool and interval.'));
      return item;
    }):[node('li','No retained OTel records for this stage.')];
    const kept=new Set(items);
    for(const item of Array.from(list.children))if(!kept.has(item))list.removeChild(item);
    for(const [index,item] of items.entries())if(list.children[index]!==item)list.insertBefore(item,list.children[index]||null);
  }
  function renderFlow(verified){
    const flow=demo.flow?.schemaVersion===1&&demo.flow.runId===demo.runId?demo.flow:null;
    if(inspection.runId!==demo.runId)inspection={runId:demo.runId,stageId:null};
    const inspected=inspection.stageId||(stages.some(([id])=>id===flow?.currentStage)?flow.currentStage:'fault');
    const now=Date.now();
    if(!get('demo-inspect-fault'))get('demo-flow-stages').replaceChildren(...stages.map(([id,label],index)=>{
      const item=node('li'),button=node('button');button.type='button';button.setAttribute('id',`demo-inspect-${id}`);button.setAttribute('aria-controls','demo-stage-inspector');
      button.append(node('span',String(index+1),'demo-stage-number'),node('strong',label),node('span','', 'demo-stage-observed'));
      button.onclick=()=>{inspection.stageId=id;render();};item.append(button);return item;
    }));
    stages.forEach(([id,label],index)=>{
      const stage=flow?.stages?.find(item=>item.id===id),workflow=stage?.workflow||'unknown';
      const button=get(`demo-inspect-${id}`),item=button.parentNode;
      item.className=`demo-flow-stage ${workflow}${id==='resolve'&&verified?' verified':''}${(display.activeStages?.[id]||0)>now?' received':''}${inspected===id?' inspecting':''}`;
      item.setAttribute('aria-current',flow?.currentStage===id?'step':'false');
      button.setAttribute('aria-pressed',inspected===id?'true':'false');
      const count=Number(stage?.observationCount)||0;
      const observed=button.children[2],copy=count?`${count} OTel observed`:workflow==='upcoming'?'No OTel yet':'No retained OTel';
      if(observed.textContent!==copy)observed.textContent=copy;
      observed.className=`demo-stage-observed${count?' observed':''}`;
      button.setAttribute('aria-label',`${index+1}. ${label}. ${workflowLabels[workflow]||'Unconfirmed'}. Inspect stage.`);
      item.title=`Workflow: ${workflow}. ${count} received OTel observation${count===1?'':'s'}.`;
    });
    renderStageDetail(flow,inspected);
    const stageKey=`${demo.runId}/${flow?.currentStage}`;
    if(inspection.stageId===null&&stageKey!==lastStage&&globalThis.matchMedia?.('(max-width:850px)').matches){const rail=get('demo-flow-stages'),index=stages.findIndex(([id])=>id===flow?.currentStage);if(index>=0)rail.scrollLeft=Math.max(0,index*104-rail.clientWidth/2+52);}
    lastStage=stageKey;
    get('demo-now-title').textContent=flow?.narrative?.title||(demo.phase==='ready'?'Ready to demonstrate.':phases[demo.phase]||'Incident state unknown.');
    get('demo-now-detail').textContent=flow?.narrative?.detail||'Waiting for correlated OTel evidence for this incident. Workflow state does not establish agent activity.';
    get('demo-now-next').textContent=flow?.narrative?.next?`Next: ${flow.narrative.next}`:'Next: received evidence will show the actual operation and its next gate.';
    const disconnected=!connected||flow?.telemetryConnected===false||flow?.mode==='disconnected';
    get('demo-flow-mode').textContent=display.replaying?'Recorded replay':disconnected?'Telemetry disconnected':flow?.mode==='unavailable'?'OTel unavailable':flow?.observations?.length?'Received OTel evidence':'Waiting for OTel';
    const viewerArrival=Number(flow?.lastViewerReceivedAt)>Number(flow?.lastReceivedAt),received=Number(viewerArrival?flow?.lastViewerReceivedAt:flow?.lastReceivedAt),age=received>0?Math.max(0,Math.floor(now/1000-received)):null;
    get('demo-flow-freshness').textContent=display.replaying?'Recorded spans, not live activity.':age===null?'No current-run OTel received.':`Last ${viewerArrival?'observed by viewer':'received'} ${age<1?'just now':`${age}s ago`}. ${display.following===false?'Inspecting a trace. Follow live to resume.':'Following this incident.'}`;
    const records=(flow?.observations||[]).slice(-12).reverse();
    get('demo-live-feed').replaceChildren(...(records.length?records.map(record=>{
      const item=node('li',undefined,`demo-live-event ${record.source==='coordinator'?'coordinator':'native'}`);
      const timestamp=Number(record.timeNs)/1e6;
      item.append(node('time',Number.isFinite(timestamp)&&timestamp>0?new Date(timestamp).toLocaleTimeString([], {hour12:false}):'Time not reported'),node('strong',record.source==='coordinator'?'Coordinator reported':'OTel observed'),node('span',record.summary||record.operation||'Operation received'));
      if(record.traceId&&retained(record.traceId))item.append(traceButton(record.traceId,'Inspect trace'));
      else if(record.traceId)item.append(node('small','Trace no longer retained'));
      return item;
    }):[node('li','No OTel received for this incident yet. The diagram stays quiet until correlated records arrive.','demo-feed-empty')]));
  }
  function render(){
    const key=JSON.stringify([demo,traces.map(trace=>[trace.traceId,trace.spans?.length]),connected,pending,approvalPending,approvalAttempt,resumePending,resumeAttempt,message,display,inspection,Math.floor(Date.now()/1000)]);
    if(key===lastRender)return;lastRender=key;
    const enabled=demo?.enabled===true;get('tab-demo').hidden=!enabled;if(!enabled)return;
    const ticket=demo.ticket||{},classifier=demo.classifier||{},native=demo.native||{},remedy=demo.remedy||{},approval=demo.approval||{},merge=demo.merge||{},verification=demo.verification||{};
    const verified=ticket.closedVerified===true&&demo.phase==='closed';
    renderFlow(verified);
    const phase=get('demo-phase');phase.textContent=verified?'Resolved · recovery verified':phases[demo.phase]||'Status unknown';phase.className=`demo-phase${verified?' verified':''}${demo.phase==='blocked'?' blocked':''}`;
    const start=get('demo-start');start.disabled=pending||approvalPending||resumePending||!connected||!hasNonce()||demo.running===true||demo.actions?.start?.enabled!==true;start.textContent=pending?'Starting…':demo.running?'Incident running':'Start demonstration';
    get('demo-start-help').textContent=!connected?'Receiver disconnected. Start is unavailable until it reconnects.':!hasNonce()?'Waiting for the receiver start token. Start is unavailable until state is refreshed.':demo.actions?.start?.reason||'Starts a real fault and follows its recovery in this lab.';
    get('demo-resume-controls').hidden=!(demo.actions?.resume&&(demo.phase==='blocked'||demo.actions.resume.enabled===true||resumeHeld()&&['observing','unknown'].includes(demo.phase)));
    const resume=get('demo-resume');resume.disabled=!canResume();resume.textContent=resumePending?'Requesting resume…':resumeHeld()?resumeAttempt.state==='accepted'?'Resume requested':resumeAttempt.state==='unknown'?'Check resume status':'Review incident':'Resume incident';
    get('demo-resume-help').textContent=!connected?'Controller disconnected. Resume is unavailable until it reconnects.':!hasNonce()?'Waiting for the controller resume token.':resumeHeld()?resumeAttempt.state==='accepted'?'Resume accepted. Following this same incident; the original failed window remains recorded.':resumeAttempt.state==='unknown'?'Resume could not be confirmed. Check the current incident state. No request will be retried automatically.':'Resume was not accepted. Review the refreshed incident state before continuing.':demo.actions?.resume?.reason||'Continue this same incident with fresh fault observations. Its original failed window stays in the history.';
    get('demo-feedback').textContent=message;
    get('demo-run').textContent=`Run ${value(demo.runId)}`;
    const humanCopy={waiting_review:'The independent review must pass before dashboard approval is available.',waiting_human:'Approve the reviewed fix here. Kagent will merge this exact commit, wait for GitOps and the application to recover, then verify recovery before resolving the issue.',merging:'Dashboard approval is recorded. Kagent is merging the approved fix.',reconciling:'Kagent has merged the approved fix. Waiting for GitOps and the application to recover.'};
    get('demo-human').hidden=!Object.hasOwn(humanCopy,demo.phase);get('demo-human').textContent=humanCopy[demo.phase]||'';
    get('demo-approval').hidden=!['waiting_human','merging'].includes(demo.phase)&&!approval.state;
    get('demo-approval-head').textContent=`Commit ${value(remedy.headSha)} · CI ${value(remedy.ci)} · Independent review ${value(remedy.review)}`;
    get('demo-approval-status').textContent=approval.state?`Approval ${value(approval.state)} · Approved by ${value(approval.approvedBy)} · Recorded ${approvalTime(approval.approvedAt)} · Expires ${approvalTime(approval.expiresAt)}`:'Your approval authorizes Kagent to merge the reviewed commit. The issue stays open until recovery is verified.';
    const approve=get('demo-approve');approve.disabled=!canApprove();approve.textContent=approvalPending?'Recording approval…':'Approve fix and let Kagent merge';
    get('demo-approve-help').textContent=!connected?'Controller disconnected. Approval is unavailable until it reconnects.':!hasNonce()?'Waiting for the controller approval token.':approvalHeld()?approvalAttempt.state==='accepted'?'Approval accepted. Following the recorded agent workflow.':approvalAttempt.state==='unknown'?'Approval outcome is unknown. Check the recorded incident state before taking further action.':'Review the refreshed fix and approval state before taking further action.':demo.actions?.approve?.reason||'Approves this exact reviewed commit for Kagent to merge.';
    link(get('demo-review'),'Open merge request in GitLab',demo.actions?.review?.enabled===true?demo.actions.review.url:remedy.mrUrl);
    link(get('demo-ticket-link'),ticket.iid?`Open GitLab issue #${ticket.iid}`:'Open GitLab issue',ticket.url);
    get('demo-ticket-state').textContent=verified?'Resolved · recovery verified':`Ticket ${value(ticket.state)} · closure not verified`;
    const descriptions={
      fault:'Start injects the configured lab fault. Observed operations appear below as the backend records them.',
      classification:`Decision ${value(classifier.decision)} · Severity ${value(classifier.severity)} · Confidence ${percent(classifier.confidence)} · Threshold ${percent(classifier.threshold)} · Attempts ${value(classifier.attempts)}`,
      kagent:`Agent ${value(native.agent)} · Task ${value(native.taskId)} · State ${value(native.state)}`,
      pr:`${value(remedy.summary)} · Head ${value(remedy.headSha)} · CI ${value(remedy.ci)} · Review ${value(remedy.review)}`,
      human:`Approval ${value(approval.state)} · Merge ${value(merge.status)} · SHA ${value(merge.sha)} · Agent task ${value(merge.taskId)} · Task state ${value(merge.taskState)}`,
      verification:`Verification task ${value(verification.taskId)} · State ${value(verification.state)} · ${verified?'Recovery and ticket closure verified.':'Recovery and ticket closure await verification.'}`
    };
    const list=get('demo-steps');list.replaceChildren(...steps.map(([id,title,active])=>{const item=node('li',undefined,`demo-step${active.includes(demo.phase)?' current':''}${id==='verification'&&verified?' verified':''}`);if(active.includes(demo.phase))item.setAttribute('aria-current','step');item.append(node('h3',title),node('p',descriptions[id]));if(id==='kagent')item.append(traceButton(native.traceId));if(id==='human')item.append(traceButton(merge.traceId,'View merge trace'));if(id==='verification')item.append(traceButton(verification.traceId,'View verification trace'));if(id==='verification'&&verification.checks){const checks=node('pre');checks.textContent=typeof verification.checks==='string'?verification.checks:JSON.stringify(verification.checks,null,2);item.append(checks);}return item;}));
    const events=Array.isArray(demo.events)?demo.events:[];get('demo-events').replaceChildren(...(events.length?events.map(event=>{const item=node('li');const time=node('time',value(event.time));item.append(time,node('strong',`${value(event.stage)} · ${value(event.state)}`),node('p',value(event.message)));if(event.traceId)item.append(traceButton(event.traceId,'View observed trace'));return item;}):[node('li','No operations recorded yet.')]));
  }
  get('demo-start').onclick=async()=>{
    if(pending||approvalPending||resumePending||!connected||!hasNonce()||demo?.running===true||demo?.actions?.start?.enabled!==true)return;
    pending=true;message='Requesting the demonstration start…';render();
    try{
      const response=await fetch('/api/demo/start',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-CSRF':demo.csrf},body:JSON.stringify({requestId:crypto.randomUUID()})});
      const body=await response.json();
      if(response.status===202){message='Start accepted. Following the recorded incident state.';adoptDemo(body.demo);}
      else{message=responseError(body,`Start was not accepted (HTTP ${response.status}). Check the current incident and model allowance.`);}
      await refreshDemo();
    }catch{message='Start could not be confirmed. Check the receiver and current incident state before trying again.';connected=false;}
    finally{pending=false;render();}
  };
  get('demo-resume').onclick=async()=>{
    if(!canResume())return;
    const submitted={requestId:crypto.randomUUID(),runId:demo.runId};
    resumeAttempt={...submitted,csrf:demo.csrf,state:'pending'};
    resumePending=true;message='Requesting fresh observations for this incident…';render();
    try{
      const response=await fetch('/api/demo/resume',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-CSRF':resumeAttempt.csrf},body:JSON.stringify(submitted)});
      const body=await response.json();
      if(response.status===202){resumeAttempt.state='accepted';message='Resume accepted. Following fresh observations for the same incident.';adoptDemo(body.demo,submitted.runId);}
      else if(response.status===409){resumeAttempt.state='conflict';message=responseError(body,'Resume was not accepted. Check the incident and model allowance.');}
      else if(response.status===400){resumeAttempt.state='invalid';message='Resume was not accepted because the request did not match the incident. Review the refreshed state.';}
      else if(response.status===403){resumeAttempt.state='forbidden';message='Resume was not accepted because the controller token changed or access was denied. Wait for refreshed state.';}
      else{resumeAttempt.state='unknown';message=`Resume could not be confirmed (HTTP ${response.status}). Check the current incident state. No request will be retried automatically.`;}
      await refreshDemo(submitted.runId);
    }catch{if(resumeAttempt.state==='pending')resumeAttempt.state='unknown';message='Resume could not be confirmed. Check the current incident state. No request will be retried automatically.';connected=false;}
    finally{resumePending=false;render();}
  };
  get('demo-approve').onclick=async()=>{
    if(!canApprove())return;
    const submitted={requestId:crypto.randomUUID(),runId:demo.runId,headSha:demo.remedy.headSha};
    approvalAttempt={runId:submitted.runId,key:approvalKey(),csrf:demo.csrf,state:'pending'};
    approvalPending=true;message='Recording approval for the displayed commit…';render();
    try{
      const response=await fetch('/api/demo/approve',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-CSRF':approvalAttempt.csrf},body:JSON.stringify(submitted)});
      if(response.status===202){approvalAttempt.state='accepted';message='Approval accepted for this exact commit.';}
      else if(response.status===409){approvalAttempt.state='conflict';message='Approval was not accepted because the reviewed fix changed. Review the refreshed incident and commit before approving.';}
      else if(response.status===400){approvalAttempt.state='invalid';message='Approval was not accepted because the request did not match the incident. Review the refreshed incident state.';}
      else if(response.status===403){approvalAttempt.state='forbidden';message='Approval was not accepted because the controller approval token changed or access was denied. Wait for refreshed state.';}
      else{approvalAttempt.state='unknown';message=`Approval could not be confirmed (HTTP ${response.status}). Check the recorded approval state. No request will be retried automatically.`;}
    }catch{approvalAttempt.state='unknown';message='Approval could not be confirmed. Check the recorded approval state. No request will be retried automatically.';connected=false;}
    finally{approvalPending=false;render();}
  };
  return {update(next,availableTraces,isConnected,viewState={}){demo=next;traces=availableTraces||[];connected=isConnected;display=viewState;render();}};
};
