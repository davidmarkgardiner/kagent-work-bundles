import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).parent
TRACE = "1" * 32
BACKGROUND = "2" * 32
HARNESS = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const input=JSON.parse(process.argv[1]),elements=new Map(),all=[];
class Element{
  constructor(tag='div'){this.tagName=tag;this.parentNode=null;this.listeners={};this.children=[];this.dataset={};this.style={};this.attributes={};this.value='';this.hidden=false;this.disabled=false;this.className='';this._text='';this.classList={toggle:(name,on)=>{const classes=new Set(this.className.split(' ').filter(Boolean));if(on)classes.add(name);else classes.delete(name);this.className=[...classes].join(' ');}};all.push(this);}
  set textContent(text){this.replaceChildren();this._text=String(text);}
  get textContent(){return this._text+this.children.map(c=>typeof c==='string'?c:c.textContent).join('');}
  append(...children){for(const child of children){if(typeof child!=='string'){if(child.parentNode)child.parentNode.removeChild(child);child.parentNode=this;}this.children.push(child);}}
  removeChild(child){this.children.splice(this.children.indexOf(child),1);child.parentNode=null;}
  insertBefore(child,reference){if(child===reference)return child;if(child.parentNode)child.parentNode.removeChild(child);const index=reference===null?this.children.length:this.children.indexOf(reference);this.children.splice(index,0,child);child.parentNode=this;return child;}
  replaceChildren(...children){for(const child of this.children)if(typeof child!=='string')child.parentNode=null;this._text='';this.children=[];this.append(...children);}
  setAttribute(key,value){this.attributes[key]=String(value);if(key==='id')elements.set(value,this);if(key==='class')this.className=String(value);}
  addEventListener(type,listener){(this.listeners[type]??=[]).push(listener);}
  dispatchEvent(event){this['on'+event.type]?.(event);for(const listener of this.listeners[event.type]||[])listener(event);}
  closest(){return this.label||(this.label=new Element('label'));}
  focus(){}
  reset(){}
  requestSubmit(){return this.onsubmit?.({preventDefault(){}});}
}
const html=fs.readFileSync('ui/index.html','utf8'),root=new Element('document'),stack=[root];
const voidTags=new Set(['meta','link','img','input','br','hr']);let end=0;
for(const match of html.matchAll(/<\/?([a-z][\w-]*)\b([^>]*?)>/gi)){
  const text=html.slice(end,match.index);if(!text.includes('<!'))stack.at(-1)._text+=text;end=match.index+match[0].length;
  if(match[0].startsWith('</')){assert.equal(stack.at(-1).tagName,match[1],`Unbalanced HTML: ${match[0]}`);stack.pop();continue;}
  const element=new Element(match[1]);
  for(const attr of match[2].matchAll(/([\w-]+)="([^"]*)"/g)){assert.ok(attr[1]!=='id'||!elements.has(attr[2]),`Duplicate ID: ${attr[2]}`);element.setAttribute(attr[1],attr[2]);}
  element.hidden=/\bhidden\b/.test(match[2]);element.open=/\bopen\b/.test(match[2]);stack.at(-1).append(element);
  if(!voidTags.has(match[1])&&!match[0].endsWith('/>'))stack.push(element);
}
assert.equal(stack.length,1,'Unclosed HTML tags');
elements.get('log-severity').value='0';elements.get('log-scope').value='all';
const calls=[];
const context=vm.createContext({document:{getElementById:id=>elements.get(id)||null,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:selectors=>all.filter(e=>selectors.split(',').some(s=>e.className.split(' ').includes(s.trim().slice(1))))},history:{replaceState(){}},location:{hash:input.state.initialHash||''},setTimeout:()=>1,clearTimeout(){},setInterval(){},Date,URL,crypto:require('node:crypto').webcrypto,console,assert,elements,calls,root,
  fetch:async(url,options)=>{calls.push({url,options});if(url==='/api/demo/approve'&&input.state.approveNetworkError||url==='/api/demo/resume'&&input.state.resumeNetworkError)throw Error('Transport unavailable');return {ok:true,status:url==='/api/demo/approve'?(input.state.approveStatus||202):url==='/api/demo/resume'?(input.state.resumeStatus||202):(input.state.startStatus||202),json:async()=>url==='/api/state'?input.state:url==='/api/demo/resume'?(input.state.resumeResponse||{}):url==='/api/demo/start'?(input.state.startResponse||{}):{revision:0,services:[],logs:[],matching:0,retained:0}};}});
vm.runInContext(fs.readFileSync('ui/demo.js','utf8'),context);
vm.runInContext(fs.readFileSync('ui/app.js','utf8'),context);
setImmediate(async()=>{try{assert.equal(elements.get('connection').textContent,'Receiver connected');await vm.runInContext('(async()=>{'+input.assertions+'})()',context);process.stdout.write('PASS UI behavior\n');}catch(error){console.error(error);process.exitCode=1;}});
"""


def ui_span(n, tool, category, execution, service="arbitrary-agent"):
    return {"traceId": TRACE, "spanId": f"{n:016x}", "parentSpanId": "", "name": "execute_tool " + tool,
            "service": service, "component": "kagent", "startNs": "1000000000", "endNs": "1100000000",
            "durationMs": 100, "status": "ok", "kind": "internal", "otelStatus": "unset",
            "toolCategory": category, "toolExecution": execution,
            "attributes": {"kagent.runtime": "adk-go", "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": tool}}


def ui_trace(trace_id=TRACE, native=True, spans=None):
    spans = spans or []
    return {"traceId": trace_id, "nativeRequest": native, "nativeRuntimeIdentity": {"runtime": "adk-go", "agentName": "arbitrary-agent", "agentId": "kagent/arbitrary-agent"} if native else None,
            "executionMode": None, "startNs": "1000000000", "durationMs": 1000, "status": "ok", "spanCount": len(spans),
            "inputTokens": None, "outputTokens": None, "usageComplete": False, "costUsd": None, "costSource": "unknown",
            "components": ["kagent", "skills"] if spans else [], "edges": [{"from": "kagent", "to": "skills", "basis": "native skill span", "spanIds": [s["spanId"] for s in spans]}] if spans else [],
            "modelCalls": [], "spans": spans}


class UiBehaviorTests(unittest.TestCase):
    def run_ui(self, state, assertions):
        result = subprocess.run(["node", "-e", HARNESS, json.dumps({"state": state, "assertions": assertions})],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_passive_viewer_selects_observed_native_request_and_separates_skills(self):
        skills = [ui_span(n, "load_skill" if n < 3 else "load_skill_resource", "skill", "native-skill") for n in range(1, 7)]
        batch = ui_span(7, "(merged tools)", "native", "native-internal")
        state = {"revision": 1, "traces": [ui_trace(BACKGROUND, False), ui_trace(spans=skills + [batch])],
                 "invocation": {"status": "idle"}, "sessionActivity": None, "nativeActivities": {},
                 "runtime": {"readOnlyViewer": True, "substrateInstalled": True, "executionTargets": [], "label": "Native viewer", "demoMode": "connected"}}
        self.run_ui(state, r"""
          assert.equal(selectedId,'11111111111111111111111111111111');
          assert.equal($('invocation-controls').hidden,true);
          assert.equal($('invocation-controls').style.display,'none');
          assert.equal($('prompt').disabled,true);assert.equal($('invoke').disabled,true);
          assert.equal($('node-skills').className.includes('observed'),true);
          assert.equal($('node-mcp').className.includes('absent'),true);
          assert.equal($('mcp-servers').children.length,0);
          assert.equal($('observed-skills').children.length,6);
          assert.match($('observed-skills').textContent,/Native ADK skill execution/);
          assert.doesNotMatch($('observed-skills').textContent,/MCP server completed/);
          assert.doesNotMatch($('observed-tools').textContent,/load_skill/);
          assert.doesNotMatch($('observed-tools').textContent,/merged tools/);
          assert.equal($('cost').textContent,'Not reported');
          assert.match($('notice').textContent,/does not establish task completion/);
          assert.match($('observed-skills').textContent,/OTel status not reported/);
          await $('prompt-form').onsubmit({preventDefault(){}});
          assert.equal(calls.filter(c=>c.url==='/api/invoke').length,0);
          selectedId='22222222222222222222222222222222';follow=false;await poll();
          assert.equal(selectedId,'22222222222222222222222222222222');
          $('follow').onclick();assert.equal(selectedId,'11111111111111111111111111111111');
        """)

    def test_external_actor_lifecycle_uses_only_backend_identity_association(self):
        activity = {"actorName": "observed-actor", "requestTraceId": TRACE, "traceIds": [TRACE, BACKGROUND],
                    "components": ["kagent", "substrate"], "edges": [],
                    "states": [{"state": "suspended", "traceId": BACKGROUND, "timestampNs": "2000000000"}]}
        state = {"revision": 1, "traces": [ui_trace(BACKGROUND, False), ui_trace()], "invocation": {"status": "idle"},
                 "sessionActivity": None, "nativeActivities": {TRACE: activity},
                 "runtime": {"readOnlyViewer": True, "executionTargets": [], "label": "Native viewer"}}
        self.run_ui(state, r"""
          assert.equal($('actor-activity').hidden,false);
          assert.equal($('actor-states').children.length,1);
          assert.equal(sessionGraph().actorName,'observed-actor');
          $('actor-states').children[0].onclick();assert.equal(selectedId,'22222222222222222222222222222222');
          assert.equal(sessionGraph(),null);
          selectedId='11111111111111111111111111111111';render();$('session-flow').onclick();
          assert.equal(selectedId,'11111111111111111111111111111111');
        """)

    def test_native_fragment_status_dot_does_not_imply_success(self):
        trace = ui_trace()
        trace.update(nativeRequest=False, status="unknown")
        state = {"revision": 1, "traces": [trace], "invocation": {"status": "idle"},
                 "sessionActivity": None, "runtime": {"readOnlyViewer": True,
                 "executionTargets": [], "label": "Native viewer"}}
        self.run_ui(state, r"""
          const dot=$('runs').children[0].children[0].children[1];
          assert.equal(dot.style.background,'var(--muted)');
          assert.match(dot.title,/completion is not inferred/);
        """)

    def test_native_totals_name_reporting_source_and_do_not_estimate_cost(self):
        native = ui_span(1, "", "", "")
        native.update(name="generate_content test-model", attributes={"kagent.runtime": "adk-go", "gen_ai.request.model": "test-model"})
        gateway = ui_span(2, "", "", "", "agentgateway")
        gateway.update(name="POST request", component="agentgateway", kind="server",
                       attributes={"gen_ai.request.model": "test-model", "gen_ai.usage.input_tokens": "15693", "gen_ai.usage.output_tokens": "1307"})
        trace = ui_trace(spans=[native, gateway])
        trace.update(modelUsageSource="native-runtime", inputTokens=15693, outputTokens=1307, usageComplete=True,
                     components=["kagent", "agentgateway", "model"], modelCalls=[{"spanId": native["spanId"]}],
                     edges=[{"from": s["component"], "to": "model", "basis": "model span", "spanIds": [s["spanId"]]} for s in (native, gateway)])
        state = {"revision": 1, "traces": [trace], "invocation": {"status": "idle"}, "sessionActivity": None,
                 "runtime": {"readOnlyViewer": True, "executionTargets": [], "label": "Native viewer", "demoMode": "connected"}}
        self.run_ui(state, r"""
          assert.match($('tokens').textContent,/15,693 \/ 1,307/);
          assert.equal($('model-usage-source').textContent,'Native runtime reports');
          assert.match($('cost-source').textContent,/Native runtime reports/);
          assert.equal($('cost').textContent,'Not reported');
          assert.equal($('timeline').children.length,1);
          filter='agentgateway';renderTimeline();assert.equal($('timeline').children.length,1);
          assert.match($('timeline').textContent,/POST request/);
          $('timeline').children[0].onclick();assert.match($('inspection').textContent,/gen_ai.usage.input_tokens15693/);
          filter=null;
          manualPrices={input:2,output:6};render();
          assert.equal($('cost').textContent,'Not reported');
          $('input-rate').value='2';$('output-rate').value='6';
          $('pricing').onsubmit({preventDefault(){}});
          assert.match($('pricing-status').textContent,/reported charges only/);
          selected().costUsd=.1;selected().costSource='reported';render();
          assert.equal($('cost').textContent,'$0.100000');
          assert.match($('cost-source').textContent,/Native runtime reports/);
          selected().inputTokens=null;selected().outputTokens=null;selected().usageComplete=false;render();
          assert.equal($('tokens').textContent,'Not reported');
          assert.equal($('model-usage-source').textContent,'Native runtime reports');
          selected().modelUsageSource='reconciled-reports';selected().inputTokens=100;selected().outputTokens=20;render();
          assert.equal($('model-usage-source').textContent,'Runtime / gateway reports');
          assert.equal($('cost').textContent,'$0.000320');
        """)

    def test_legacy_mcp_server_completion_is_preserved(self):
        tool = ui_span(1, "k8s_get_resources", "mcp", "server", "flow-kubernetes-mcp")
        tool.update(component="mcp", kind="server", otelStatus="ok")
        trace = ui_trace(native=False, spans=[tool])
        trace.update(components=["mcp"], edges=[])
        state = {"revision": 1, "traces": [trace], "invocation": {"status": "idle"}, "sessionActivity": None,
                 "runtime": {"executionTargets": [{"id": "agent", "mode": "a2a", "label": "Configured agent"}], "label": "Legacy viewer"}}
        self.run_ui(state, r"""
          assert.equal($('prompt').disabled,false);assert.equal($('invoke').disabled,false);
          assert.equal($('invocation-controls').hidden,false);
          assert.equal($('mcp-servers').children.length,1);
          assert.match($('mcp-servers').textContent,/MCP server completed/);
          assert.match($('observed-tools').textContent,/k8s_get_resources/);
        """)


class DemoUiTests(UiBehaviorTests):
    def demo_state(self, **demo):
        return {"revision": 1, "traces": [], "invocation": {"status": "idle"}, "nativeActivities": {}, "runtime": {"readOnlyViewer": True, "executionTargets": [], "label": "Test"}, "demo": {"enabled": True, "csrf": "state-csrf-nonce", "phase": "ready", "running": False, "actions": {"start": {"enabled": True}}, **demo}}

    def approval_state(self, **demo):
        return self.demo_state(phase='waiting_human', running=True, runId='run-under-review',
            remedy={'mrUrl':'https://gitlab.com/a/b/-/merge_requests/2','headSha':'a'*40,'ci':'passed','review':'passed'},
            actions={'start':{'enabled':False},'approve':{'enabled':True}}, **demo)

    def flow_state(self):
        span=ui_span(1,'load_skill','skill','native-skill')
        state=self.demo_state(runId='run-current',phase='triaging',running=True)
        state['traces']=[ui_trace(BACKGROUND,False),ui_trace(spans=[span])]
        state['demo']['flow']={'schemaVersion':1,'runId':'run-current','currentStage':'triage','mode':'live','telemetryConnected':True,'lastReceivedAt':None,
            'stages':[{'id':'triage','workflow':'active','observationCount':1,'telemetry':'recorded'}],
            'narrative':{'title':'Kagent is investigating.','detail':'Waiting for native task evidence.','next':'Review the remedy.'},
            'scope':{'traceIds':[TRACE],'spanIds':{TRACE:[span['spanId']]},'activeTraceId':TRACE,'components':['kagent','skills'],'edges':[{**edge,'traceIds':[TRACE]} for edge in state['traces'][1]['edges']]},
            'observations':[]}
        return state

    def test_demo_embeds_graph_and_follows_run_without_leaving_demo(self):
        self.run_ui(self.flow_state(),r"""
          assert.equal(currentView,'demo');assert.equal($('runtime-flow').parentNode,$('demo-flow-slot'));
          assert.equal(selectedId,'11111111111111111111111111111111');assert.equal($('demo-flow-stages').children.length,9);
          assert.equal($('runtime-details').open,false);assert.equal($('runtime-operations').open,false);
          assert.equal($('demo-now-title').textContent,'Kagent is investigating.');assert.match($('demo-now-next').textContent,/Review the remedy/);
          selectTrace(selectedId);assert.equal(currentView,'demo');assert.equal(follow,false);assert.equal($('follow').disabled,false);
          assert.equal($('follow').textContent,'Follow live');assert.equal($('runtime-details').open,true);
          $('follow').onclick();assert.equal(follow,true);assert.equal(currentView,'demo');
          state.traces[0].spans=[{...state.traces[1].spans[0],traceId:'22222222222222222222222222222222'}];state.demo.flow.scope.activeTraceId='22222222222222222222222222222222';await poll();
          assert.equal(selectedId,'22222222222222222222222222222222');assert.equal(currentView,'demo');
        """)

    def test_all_nine_stage_buttons_show_their_own_history_without_actions(self):
        state=self.flow_state()
        ids=['fault','classify','triage','review','approval','merge','recovery','verify','resolve']
        state['demo']['flow']['stages']=[{'id':stage,'workflow':'passed','observationCount':0,
            'controllerEvents':[{'step':stage,'state':'completed','time':'2026-11-01T17:00:00Z','message':'Recorded '+stage}]} for stage in ids]
        self.run_ui(state,r"""
          const ids=['fault','classify','triage','review','approval','merge','recovery','verify','resolve'];
          for(const [index,id] of ids.entries()){
            const button=$('demo-inspect-'+id);assert.equal(button.tagName,'button');assert.equal(button.type,'button');
            button.onclick();assert.equal(button.attributes['aria-pressed'],'true');
            assert.match($('demo-stage-title').textContent,new RegExp('^'+(index+1)+'\\. '));
            assert.equal($('demo-stage-outcome').textContent,'Recorded '+id);
            assert.equal($('demo-stage-history').children.length,1);
            assert.match($('demo-stage-coverage').textContent,/No retained OTel/);
          }
          assert.equal(calls.filter(call=>call.options?.method==='POST').length,0);
          assert.equal($('demo-inspect-triage').parentNode.attributes['aria-current'],'step');
          assert.equal($('demo-inspect-resolve').parentNode.attributes['aria-current'],'false');
        """)

    def test_stage_selection_survives_polls_preserves_button_and_resets_on_new_run(self):
        self.run_ui(self.flow_state(),r"""
          const button=$('demo-inspect-fault'),number=button.children[0];button.onclick();
          state.demo.flow.currentStage='verify';state.demo.flow.stages.push({id:'verify',workflow:'active'});
          await poll();assert.equal($('demo-inspect-fault'),button);
          assert.equal(button.children[0],number);
          assert.match($('demo-stage-title').textContent,/^1\. Fault/);
          assert.equal(button.attributes['aria-pressed'],'true');assert.equal($('demo-stage-follow').hidden,false);
          $('demo-stage-follow').onclick();assert.match($('demo-stage-title').textContent,/^8\. Verify/);
          assert.equal($('demo-stage-follow').hidden,true);
          button.onclick();state.demo.runId='new-run';state.demo.flow={...state.demo.flow,runId:'new-run',currentStage:'approval'};
          await poll();assert.match($('demo-stage-title').textContent,/^5\. Your approval/);
          assert.equal($('demo-stage-follow').hidden,true);
        """)

    def test_stage_components_and_trace_links_use_stage_records_and_exact_retained_span(self):
        state=self.flow_state()
        state['demo']['flow']['observations']=[
            {'id':'skill','stageId':'triage','component':'skills','source':'native','summary':'Native skill read','traceId':TRACE,'spanId':'0000000000000001'},
            {'id':'model','stageId':'verify','component':'model','source':'native','summary':'Another stage model','traceId':TRACE,'spanId':'0000000000000002'},
            {'id':'controller','stageId':'triage','component':'client','source':'coordinator','summary':'Receipt only','traceId':None}]
        self.run_ui(state,r"""
          assert.match($('demo-stage-components').textContent,/Skills & knowledge/);
          assert.match($('demo-stage-components').textContent,/Demo controller/);
          assert.doesNotMatch($('demo-stage-components').textContent,/Model|MCP tools/);
          assert.equal($('demo-stage-otel').children.flatMap(item=>item.children).filter(item=>item.tagName==='button').length,1);
          const traceButton=$('demo-stage-otel').children.flatMap(item=>item.children).find(item=>item.tagName==='button');
          const row=traceButton.parentNode;await poll();assert.equal(traceButton.parentNode,row);assert.equal(row.parentNode,$('demo-stage-otel'));
          state.demo.flow.observations.push({id:'new','stageId':'triage',component:'model',source:'native',summary:'A newly received observation'});
          await poll();assert.equal(traceButton.parentNode,row);assert.equal(row.parentNode,$('demo-stage-otel'));
          assert.equal($('demo-stage-otel').children.flatMap(item=>item.children).find(item=>item.tagName==='button'),traceButton);
          $('demo-inspect-verify').onclick();assert.match($('demo-stage-components').textContent,/Model/);
          assert.doesNotMatch($('demo-stage-components').textContent,/Skills|Demo controller/);
          assert.equal($('demo-stage-otel').children.flatMap(item=>item.children).filter(item=>item.tagName==='button').length,0);
          assert.match($('demo-stage-otel').textContent,/Matching span is no longer retained/);
          state.demo.flow.observations=[];await poll();assert.match($('demo-stage-components').textContent,/No retained component telemetry/);
          assert.equal(calls.filter(call=>call.options?.method==='POST').length,0);
        """)

    def test_stage_inspector_rejects_stale_run_flow_and_keeps_future_stage_honest(self):
        state=self.flow_state()
        state['demo']['flow']['stages'].append({'id':'resolve','workflow':'upcoming','controllerEvents':[]})
        self.run_ui(state,r"""
          $('demo-inspect-resolve').onclick();assert.equal($('demo-stage-status').textContent,'Not started');
          assert.match($('demo-stage-outcome').textContent,/No operation recorded/);
          assert.match($('demo-stage-facts').textContent,/Not verified/);
          state.demo.flow.runId='old-run';state.demo.flow.observations=[{stageId:'resolve',component:'model'}];await poll();
          assert.match($('demo-stage-components').textContent,/No retained component telemetry/);
          assert.equal($('demo-stage-history').children.length,1);
          assert.match($('demo-stage-history').textContent,/No retained controller receipts/);
        """)

    def test_flow_changes_render_without_trace_revision_and_wrong_run_is_quiet(self):
        self.run_ui(self.flow_state(),r"""
          state.demo.flow.narrative.title='Waiting for your approval.';await poll();
          assert.equal($('demo-now-title').textContent,'Waiting for your approval.');
          state.demo.runId='different-run';await poll();assert.equal(selectedId,null);
          assert.equal($('node-kagent').className.includes('absent'),true);assert.equal(activeNodes.size,0);
          assert.match($('demo-live-feed').textContent,/No OTel received/);
          assert.equal($('demo-flow-stages').children.some(item=>item.className.includes('verified')),false);
        """)

    def test_recent_observations_only_pulse_after_baseline_and_coordinator_only_caller(self):
        self.run_ui(self.flow_state(),r"""
          assert.equal(activeNodes.size,0);
          const record=(id,source,kind='span')=>({id,kind,source,stageId:'triage',component:'kagent',operation:'load_skill',summary:'Actual metadata',traceId:selectedId,spanId:'0000000000000001',timeNs:String((Date.now()-100)*1e6),endNs:String((Date.now()-100)*1e6),receivedAt:(Date.now()-100)/1000,recent:true});
          state.demo.flow.observations.push(record('first','native'));await poll();
          assert.equal(activeNodes.has('skills'),true);assert.equal(activeStages.has('triage'),true);
          activeNodes.clear();activeEdges.clear();await poll();assert.equal(activeNodes.size,0);
          state.demo.flow.observations=[];await poll();state.demo.flow.observations=[record('first','native')];await poll();assert.equal(activeNodes.size,0);
          state.demo.flow.observations.push(record('owned-log','coordinator','log'));await poll();
          assert.equal(activeNodes.has('client'),true);assert.equal(activeNodes.has('kagent'),false);assert.equal(activeEdges.size,0);
          assert.match($('demo-live-feed').textContent,/Coordinator reported/);
          activeNodes.clear();state.demo.flow.observations.push({...record('old','native'),receivedAt:Date.now()/1000-60});await poll();assert.equal(activeNodes.size,0);
          state.demo.flow.observations.push({...record('old-event','native'),endNs:'1100000000'});await poll();assert.equal(activeNodes.size,0);
          state.demo.flow.observations.push({...record('future','native'),receivedAt:Date.now()/1000+30});await poll();assert.equal(activeNodes.size,0);
        """)

    def test_demo_evidence_excludes_uncorrelated_spans_inside_a_matched_trace(self):
        state=self.flow_state()
        orphan=ui_span(2,'unrelated_secret_tool','mcp','server','unrelated-backend')
        state['traces'][1]['spans'].append(orphan)
        self.run_ui(state,r"""
          assert.equal(scopedSpans().length,1);
          assert.doesNotMatch($('observed-tools').textContent,/unrelated_secret_tool/);
          selectTrace(selectedId);assert.equal(follow,false);assert.equal(scopedSpans().length,2);
          assert.equal($('mode').textContent,'Trace inspection');
          $('follow').onclick();assert.equal(scopedSpans().length,1);
        """)

    def mcp_edge_state(self):
        state=self.flow_state()
        span=ui_span(2,'read_policy_repository','mcp','server','kyverno-gitlab-mcp');span['component']='mcp'
        state['traces'][1]['spans'].append(span);state['traces'][1]['edges']=[]
        state['demo']['flow']['scope']['spanIds'][TRACE].append(span['spanId'])
        state['demo']['flow']['scope']['components'].append('mcp')
        state['demo']['flow']['scope']['edges']=[{'from':'kagent','to':'mcp','basis':'same trace, tool and interval (parent missing)','spanIds':['0000000000000001',span['spanId']],'traceIds':[TRACE]}]
        return state

    def test_actual_mcp_arrival_pulses_verified_scope_edge_without_raw_parent_edge(self):
        self.run_ui(self.mcp_edge_state(),r"""
          assert.equal(activeNodes.size,0);
          const now=Date.now()-100;
          state.demo.flow.observations.push({id:'actual-server',kind:'span',source:'mcp',stageId:'triage',traceId:selectedId,spanId:'0000000000000002',timeNs:String(now*1e6),endNs:String(now*1e6),receivedAt:now/1000,recent:true});
          await poll();assert.equal(activeNodes.has('mcp'),true);assert.equal(activeNodes.has('kagent'),true);
          assert.equal(activeEdges.has('kagent-mcp'),true);
          assert.equal(state.traces[1].edges.length,0);
        """)

    def test_mcp_edge_pulses_require_its_exact_trace_and_observed_span(self):
        for invalid in ('trace','span','unselected','inspection'):
            state=self.mcp_edge_state();state['invalidEdge']=invalid
            self.run_ui(state,r"""
              const edge=state.demo.flow.scope.edges[0];
              if(state.invalidEdge==='trace')edge.traceIds=['22222222222222222222222222222222'];
              if(state.invalidEdge==='span')edge.spanIds=['0000000000000001'];
              if(state.invalidEdge==='unselected')state.demo.flow.scope.spanIds[selectedId]=['0000000000000001'];
              if(state.invalidEdge==='inspection')selectTrace(selectedId);
              const now=Date.now()-100;
              state.demo.flow.observations.push({id:'actual-server',kind:'span',source:'mcp',stageId:'triage',traceId:selectedId,spanId:'0000000000000002',timeNs:String(now*1e6),endNs:String(now*1e6),receivedAt:now/1000,recent:true});
              await poll();assert.equal(activeEdges.has('kagent-mcp'),false);
              if(state.invalidEdge==='unselected')assert.equal(activeNodes.size,0);
            """)

    def test_legacy_log_arrival_pulses_owned_caller_with_honest_freshness(self):
        self.run_ui(self.flow_state(),r"""
          const now=Date.now()-100;
          state.demo.flow.lastReceivedAt=null;state.demo.flow.lastViewerReceivedAt=now/1000;
          state.demo.flow.observations.push({id:'legacy-start',kind:'log',source:'coordinator',stageId:'fault',component:'client',operation:'demo.observe_fault',summary:'Controller · Inject and observe fault · started',traceId:null,spanId:'',timeNs:String(now*1e6),endNs:String(now*1e6),receivedAt:null,viewerReceivedAt:now/1000,receiptSource:'viewer',recent:true});
          await poll();assert.equal(activeNodes.has('client'),true);assert.equal(activeNodes.has('kagent'),false);assert.equal(activeEdges.size,0);
          assert.match($('demo-flow-freshness').textContent,/Last observed by viewer/);
          assert.match($('demo-live-feed').textContent,/Inject and observe fault/);
        """)

    def test_first_snapshot_does_not_pulse_and_evicted_trace_metadata_remains(self):
        state=self.flow_state()
        import time
        now=time.time()
        state['demo']['flow']['observations']=[{'id':'retained','kind':'span','source':'native','stageId':'triage','traceId':TRACE,'spanId':'0000000000000001','timeNs':str(int(now*1e9)),'endNs':str(int(now*1e9)),'receivedAt':now,'summary':'<script>metadata only</script>','recent':True}]
        self.run_ui(state,r"""
          assert.equal(activeNodes.size,0);assert.match($('demo-live-feed').textContent,/<script>metadata only/);
          state.traces=[];await poll();assert.equal(selectedId,null);
          assert.match($('demo-live-feed').textContent,/Trace no longer retained/);assert.equal(activeNodes.size,0);
          assert.equal($('mode').textContent.includes('LIVE'),false);
        """)

    def test_recorded_replay_is_explicit_and_receiver_disconnect_is_visible(self):
        self.run_ui(self.flow_state(),r"""
          $('replay').onclick();assert.equal(replaying,true);assert.equal($('mode').textContent,'Recorded replay');
          assert.equal($('demo-flow-mode').textContent,'Recorded replay');assert.match($('demo-flow-freshness').textContent,/not live/);
          stopReplay();state.demo.flow.telemetryConnected=false;render();assert.equal($('mode').textContent,'Disconnected');
          assert.equal($('demo-flow-mode').textContent,'Telemetry disconnected');assert.equal(calls.filter(call=>call.options?.method==='POST').length,0);
        """)

    def test_demo_defaults_and_no_fake_spans(self):
        self.run_ui(self.demo_state(), r"""
          assert.equal(currentView,'demo');assert.equal($('tab-demo').hidden,false);
          assert.equal($('prompt-column').hidden,true);assert.equal($('demo-start').disabled,false);
          assert.equal($('demo-steps').children.length,6);assert.equal($('node-kagent').className.includes('absent'),true);
          assert.match($('demo-steps').textContent,/Confidence Not reported/);
          $('tab-demo').onkeydown({key:'ArrowRight',preventDefault(){}});assert.equal(currentView,'visual');
          $('tab-visual').onclick();await poll();assert.equal(currentView,'visual');
        """)

    def test_explicit_hash_and_disabled_demo_preserve_existing_navigation(self):
        state=self.demo_state();state['initialHash']='#logs'
        self.run_ui(state,r"""
          assert.equal(currentView,'logs');await poll();assert.equal(currentView,'logs');
        """)
        state=self.demo_state(enabled=False);state['initialHash']='#demo'
        self.run_ui(state,r"""
          assert.equal(currentView,'visual');assert.equal($('tab-demo').hidden,true);
          $('tab-recovery').onkeydown({key:'ArrowRight',preventDefault(){}});assert.equal(currentView,'visual');
        """)

    def test_start_payload_and_duplicate_click(self):
        self.run_ui(self.demo_state(), r"""
          const first=$('demo-start').onclick();const second=$('demo-start').onclick();await Promise.all([first,second]);
          const posts=calls.filter(c=>c.url==='/api/demo/start');assert.equal(posts.length,1);
          assert.equal(posts[0].options.method,'POST');assert.equal(posts[0].options.headers['X-Demo-CSRF'],'state-csrf-nonce');assert.deepEqual(Object.keys(JSON.parse(posts[0].options.body)),['requestId']);
          assert.match(JSON.parse(posts[0].options.body).requestId,/^[a-f0-9-]{36}$/);
          assert.equal(posts[0].options.credentials,undefined);assert.equal($('demo-start').disabled,false);
          assert.match($('demo-feedback').textContent,/Start accepted/);
        """)

    def resume_state(self, enabled=True, reason=None, **demo):
        return self.demo_state(runId='run-stopped',phase='blocked',running=False,
            actions={'start':{'enabled':False,'reason':'This incident stopped before classification.'},
                     'resume':{'enabled':enabled,'reason':reason}},**demo)

    def test_resume_payload_and_duplicate_click_hold_one_request(self):
        self.run_ui(self.resume_state(),r"""
          assert.equal($('demo-resume-controls').hidden,false);assert.equal($('demo-resume').disabled,false);
          const first=$('demo-resume').onclick();const second=$('demo-resume').onclick();await Promise.all([first,second]);
          const posts=calls.filter(c=>c.url==='/api/demo/resume');assert.equal(posts.length,1);
          const submitted=JSON.parse(posts[0].options.body);assert.deepEqual(Object.keys(submitted),['requestId','runId']);
          assert.equal(submitted.runId,'run-stopped');assert.match(submitted.requestId,/^[a-f0-9-]{36}$/);
          assert.equal(posts[0].options.method,'POST');assert.equal(posts[0].options.headers['X-Demo-CSRF'],'state-csrf-nonce');
          assert.equal(posts[0].options.headers['Content-Type'],'application/json');assert.equal(posts[0].options.credentials,undefined);
          assert.equal($('demo-resume').disabled,true);assert.equal($('demo-phase').textContent,'Blocked');
          assert.match($('demo-feedback').textContent,/Resume accepted/);assert.match($('demo-resume-help').textContent,/original failed window remains/);
          await poll();await $('demo-resume').onclick();assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,1);
          assert.equal(calls.filter(c=>c.url==='/api/demo/approve').length,0);
          state.demo.phase='triaging';state.demo.actions.resume.enabled=false;await poll();assert.equal($('demo-resume-controls').hidden,true);
        """)

    def test_resume_budget_reason_and_missing_nonce_prevent_posts(self):
        self.run_ui(self.resume_state(False,'The existing model allowance is exhausted; operator authorization is required.'),r"""
          assert.equal($('demo-resume').disabled,true);assert.match($('demo-resume-help').textContent,/allowance is exhausted/);
          await $('demo-resume').onclick();assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,0);
          state.demo.actions.resume.enabled=true;state.demo.csrf=null;render();assert.equal($('demo-resume').disabled,true);
          await $('demo-resume').onclick();assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,0);
          assert.match($('demo-resume-help').textContent,/controller resume token/);
          state.demo.csrf='new-token';receiverConnected=false;render();assert.equal($('demo-resume').disabled,true);
          assert.match($('demo-resume-help').textContent,/disconnected/);
        """)

    def test_definitive_resume_rejection_allows_manual_retry_after_fresh_eligibility(self):
        state=self.resume_state();state['resumeStatus']=409
        self.run_ui(state,r"""
          await $('demo-resume').onclick();assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,1);
          state.demo.actions.resume.enabled=true;state.demo.csrf='new-controller-token';await poll();
          assert.equal($('demo-resume').disabled,false);
          assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,1);
          state.resumeStatus=202;await $('demo-resume').onclick();
          assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,2);
          assert.equal($('demo-resume').disabled,true);
        """)

    def test_resume_unknown_response_never_retries_after_state_poll(self):
        state=self.resume_state();state['resumeStatus']=503
        self.run_ui(state,r"""
          await $('demo-resume').onclick();assert.equal($('demo-resume').disabled,true);
          assert.match($('demo-feedback').textContent,/HTTP 503/);assert.equal($('demo-resume').textContent,'Check resume status');assert.match($('demo-resume-help').textContent,/No request will be retried automatically/);
          await poll();await $('demo-resume').onclick();
          assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,1);assert.equal($('demo-phase').textContent,'Blocked');
        """)

    def test_resume_network_error_remains_held_after_reconnection(self):
        state=self.resume_state();state['resumeNetworkError']=True
        self.run_ui(state,r"""
          await $('demo-resume').onclick();assert.equal($('demo-resume').disabled,true);
          assert.match($('demo-feedback').textContent,/could not be confirmed/);
          state.resumeNetworkError=false;await poll();await $('demo-resume').onclick();
          assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,1);
        """)

    def test_resume_reads_actual_returned_state_and_retains_current_token(self):
        self.run_ui(self.resume_state(),r"""
          const actual={...state.demo,phase:'observing',running:true,actions:{start:{enabled:false},resume:{enabled:false}}};
          fetch=async(url,options)=>{calls.push({url,options});return {ok:true,status:202,json:async()=>url==='/api/state'?{...state,demo:actual}:{demo:{...actual,csrf:undefined}}};};
          await $('demo-resume').onclick();assert.equal($('demo-phase').textContent,'Observing fault');
          assert.equal($('demo-start').textContent,'Incident running');assert.equal($('demo-resume').disabled,true);
          assert.equal(calls.filter(c=>c.url==='/api/state').length,2);
          assert.equal(calls.filter(c=>c.url==='/api/demo/start'||c.url==='/api/demo/approve').length,0);
        """)

    def test_resume_reply_for_another_run_cannot_replace_current_incident(self):
        state=self.resume_state();state['resumeResponse']={'demo':{'enabled':True,'runId':'different-run','phase':'closed','running':False,'ticket':{'closedVerified':True}}}
        self.run_ui(state,r"""
          await $('demo-resume').onclick();assert.equal($('demo-phase').textContent,'Blocked');
          assert.equal($('demo-phase').className.includes('verified'),false);assert.match($('demo-run').textContent,/run-stopped/);
        """)

    def test_resume_requires_explicit_blocked_phase_and_action(self):
        self.run_ui(self.demo_state(),r"""
          assert.equal($('demo-resume-controls').hidden,true);await $('demo-resume').onclick();
          assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,0);
          state.demo.actions.resume={enabled:true};state.demo.runId='new-run';state.demo.phase='unknown';render();await $('demo-resume').onclick();
          assert.equal(calls.filter(c=>c.url==='/api/demo/resume').length,0);
        """)

    def test_missing_nonce_blocks_start_and_uses_latest_nonce(self):
        self.run_ui(self.demo_state(csrf=None),r"""
          assert.equal($('demo-start').disabled,true);await $('demo-start').onclick();
          assert.equal(calls.filter(call=>call.url==='/api/demo/start').length,0);
          assert.match($('demo-start-help').textContent,/Waiting for the receiver start token/);
          state.demo.csrf='refreshed-state-nonce';render();assert.equal($('demo-start').disabled,false);
          await $('demo-start').onclick();assert.equal(calls.find(call=>call.url==='/api/demo/start').options.headers['X-Demo-CSRF'],'refreshed-state-nonce');
        """)

    def test_start_budget_conflict_preserves_stopped_state_without_retry(self):
        state=self.demo_state(runId='stopped-run',phase='blocked');state['startStatus']=409
        state['startResponse']={'error':'The model allowance is exhausted; no new fault was created.'}
        self.run_ui(state, r"""
          await $('demo-start').onclick();assert.match($('demo-feedback').textContent,/model allowance is exhausted/);
          assert.equal($('demo-phase').textContent,'Blocked');assert.equal($('demo-start').textContent,'Start demonstration');
          assert.equal(calls.filter(c=>c.url==='/api/demo/start').length,1);assert.equal(calls.filter(c=>c.url==='/api/state').length,2);
          assert.equal(state.demo.running,false);assert.doesNotMatch($('demo-feedback').textContent,/already active/);
        """)

    def test_error_is_visible_and_recoverable(self):
        state=self.demo_state();state['startStatus']=503
        self.run_ui(state, r"""
          await $('demo-start').onclick();assert.match($('demo-feedback').textContent,/HTTP 503/);
          assert.equal($('demo-start').disabled,false);
        """)

    def test_human_boundary_urls_and_closed_gate(self):
        self.run_ui(self.demo_state(phase='waiting_human',classifier={'confidence':0.92,'threshold':0.85},ticket={'state':'closed','closedVerified':False,'url':'javascript:alert(1)'},remedy={'mrUrl':'https://gitlab.com/a/b/-/merge_requests/1','headSha':'abc123','ci':'passed','review':'pending'},native={'traceId':'missing'},events=[{'stage':'fault','state':'injected','message':'<script>bad()</script>'}]),r"""
          assert.equal($('demo-human').hidden,false);assert.match($('demo-steps').textContent,/92.0%/);
          assert.equal($('demo-review').children[0].href,'https://gitlab.com/a/b/-/merge_requests/1');
          assert.equal($('demo-ticket-link').children[0].tagName,'span');
          assert.equal($('demo-phase').className.includes('verified'),false);
          assert.match($('demo-ticket-state').textContent,/closure not verified/);
          assert.equal($('demo-steps').children[2].children[2].disabled,true);
          assert.match($('demo-events').textContent,/<script>bad/);
          state.demo.ticket.closedVerified=true;render();assert.equal($('demo-phase').className.includes('verified'),false);state.demo.phase='closed';render();assert.equal($('demo-phase').className.includes('verified'),true);
          state.demo.ticket.url='https://gitlab.com.evil.test/a';render();assert.equal($('demo-ticket-link').children[0].tagName,'span');
        """)

    def test_office_gitlab_links_require_the_exact_configured_https_origin(self):
        self.run_ui(self.demo_state(gitlabOrigin='https://gitlab.office.example.invalid:8443',
            remedy={'mrUrl':'https://gitlab.office.example.invalid:8443/a/b/-/merge_requests/1'},
            ticket={'url':'https://gitlab.office.example.invalid:8443/a/b/-/issues/1'}),r"""
          assert.equal($('demo-review').children[0].tagName,'a');assert.equal($('demo-ticket-link').children[0].tagName,'a');
          for(const url of ['http://gitlab.office.example.invalid:8443/a','https://gitlab.office.example.invalid/a',
            'https://gitlab.office.example.invalid.evil.test:8443/a','https://user:secret@gitlab.office.example.invalid:8443/a',
            'https://gitlab.com/a','javascript:alert(1)']){
            state.demo.ticket.url=url;render();assert.equal($('demo-ticket-link').children[0].tagName,'span');
          }
          state.demo.gitlabOrigin='https://gitlab.office.example.invalid:443';state.demo.ticket.url='https://gitlab.office.example.invalid/a';render();
          assert.equal($('demo-ticket-link').children[0].tagName,'a');
          for(const origin of [null,'','http://gitlab.com','https://user:secret@gitlab.com','https://gitlab.com/api/v4']){
            state.demo.gitlabOrigin=origin;state.demo.ticket.url='https://gitlab.com/a';render();assert.equal($('demo-ticket-link').children[0].tagName,'span');
          }
          delete state.demo.gitlabOrigin;render();assert.equal($('demo-ticket-link').children[0].tagName,'a');
          assert.equal(calls.filter(call=>call.options?.method==='POST').length,0);
        """)

    def test_trace_opens_only_retained_spans_and_disconnect_blocks_start(self):
        span=ui_span(1,'probe','mcp','server');state=self.demo_state(native={'taskId':'task-1','traceId':TRACE});state['traces']=[ui_trace(spans=[span])]
        self.run_ui(state,r"""
          const button=$('demo-steps').children[2].children[2];assert.equal(button.disabled,false);button.onclick();
          assert.equal(currentView,'demo');assert.equal(selectedId,'11111111111111111111111111111111');assert.equal(follow,false);assert.equal($('runtime-flow').parentNode,$('demo-flow-slot'));
          receiverConnected=false;render();assert.equal($('demo-start').disabled,true);
          assert.match($('demo-start-help').textContent,/disconnected/);
        """)

    def test_dashboard_approval_requires_human_click_and_displays_reviewed_head(self):
        self.run_ui(self.approval_state(), r"""
          assert.equal($('demo-phase').textContent,'Waiting for dashboard approval');
          assert.equal($('demo-approval').hidden,false);assert.equal($('demo-approve').disabled,false);
          assert.equal($('demo-start').disabled,true);
          assert.equal($('demo-approve').textContent,'Approve fix and let Kagent merge');
          assert.match($('demo-approval-head').textContent,/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/);
          assert.match($('demo-approval-head').textContent,/CI passed.*Independent review passed/);
          assert.match($('demo-human').textContent,/Kagent will merge this exact commit/);
          assert.doesNotMatch($('demo-human').textContent,/review and merge in GitLab/);
          assert.equal(calls.filter(call=>call.options?.method==='POST').length,0);
        """)

    def test_approval_posts_exact_displayed_target_once_without_browser_identity(self):
        self.run_ui(self.approval_state(), r"""
          const first=$('demo-approve').onclick();const second=$('demo-approve').onclick();
          state.demo.remedy.headSha='b'.repeat(40);await Promise.all([first,second]);
          const posts=calls.filter(call=>call.url==='/api/demo/approve');assert.equal(posts.length,1);
          const body=JSON.parse(posts[0].options.body);
          assert.deepEqual(Object.keys(body),['requestId','runId','headSha']);
          assert.equal(body.runId,'run-under-review');assert.equal(body.headSha,'a'.repeat(40));
          assert.match(body.requestId,/^[a-f0-9-]{36}$/);
          assert.equal(posts[0].options.method,'POST');
          assert.equal(posts[0].options.headers['X-Demo-CSRF'],'state-csrf-nonce');
          assert.equal(posts[0].options.headers['Content-Type'],'application/json');
          assert.equal($('demo-approve').disabled,true);assert.match($('demo-feedback').textContent,/Approval accepted/);
          await poll();await $('demo-approve').onclick();
          assert.equal(calls.filter(call=>call.url==='/api/demo/approve').length,1);
          assert.equal(calls.filter(call=>/merge/.test(call.url)).length,0);
        """)

    def test_approval_requires_nonce_target_and_passing_review(self):
        mutations = [('csrf',None),('runId',None),('headSha','short'),('ci','pending'),('review','pending'),('approve',False)]
        for field,value in mutations:
            with self.subTest(field=field):
                state=self.approval_state()
                if field in ('headSha','ci','review'):state['demo']['remedy'][field]=value
                elif field=='approve':state['demo']['actions']['approve']['enabled']=value
                else:state['demo'][field]=value
                self.run_ui(state,r"""
                  assert.equal($('demo-approve').disabled,true);await $('demo-approve').onclick();
                  assert.equal(calls.filter(call=>call.url==='/api/demo/approve').length,0);
                """)

    def test_disconnection_blocks_approval(self):
        self.run_ui(self.approval_state(),r"""
          receiverConnected=false;render();assert.equal($('demo-approve').disabled,true);
          assert.match($('demo-approve-help').textContent,/disconnected/);
          await $('demo-approve').onclick();assert.equal(calls.filter(call=>call.url==='/api/demo/approve').length,0);
        """)

    def test_changed_head_conflict_requires_review_and_another_explicit_click(self):
        state=self.approval_state();state['approveStatus']=409
        self.run_ui(state,r"""
          await $('demo-approve').onclick();assert.match($('demo-feedback').textContent,/reviewed fix changed/);
          await poll();await $('demo-approve').onclick();
          assert.equal(calls.filter(call=>call.url==='/api/demo/approve').length,1);
          state.demo.remedy.headSha='b'.repeat(40);render();assert.equal($('demo-approve').disabled,false);
          assert.equal(calls.filter(call=>call.url==='/api/demo/approve').length,1);
        """)

    def test_invalid_approval_request_is_visible_and_not_retried(self):
        state=self.approval_state();state['approveStatus']=400
        self.run_ui(state,r"""
          await $('demo-approve').onclick();assert.match($('demo-feedback').textContent,/request did not match/);
          await poll();await $('demo-approve').onclick();
          assert.equal(calls.filter(call=>call.url==='/api/demo/approve').length,1);
        """)

    def test_forbidden_approval_waits_for_refreshed_nonce(self):
        state=self.approval_state();state['approveStatus']=403
        self.run_ui(state,r"""
          await $('demo-approve').onclick();assert.match($('demo-feedback').textContent,/token changed or access was denied/);
          await poll();assert.equal($('demo-approve').disabled,true);
          state.demo.csrf='refreshed-approval-nonce';render();assert.equal($('demo-approve').disabled,false);
          assert.equal(calls.filter(call=>call.url==='/api/demo/approve').length,1);
        """)

    def test_unknown_approval_response_never_retries_on_refresh(self):
        state=self.approval_state();state['approveStatus']=502
        self.run_ui(state,r"""
          await $('demo-approve').onclick();assert.match($('demo-feedback').textContent,/HTTP 502/);
          assert.match($('demo-feedback').textContent,/No request will be retried automatically/);
          await poll();await $('demo-approve').onclick();assert.equal($('demo-approve').disabled,true);
          assert.equal(calls.filter(call=>call.url==='/api/demo/approve').length,1);
        """)

    def test_lost_approval_response_never_retries_when_connection_returns(self):
        state=self.approval_state();state['approveNetworkError']=True
        self.run_ui(state,r"""
          await $('demo-approve').onclick();assert.match($('demo-feedback').textContent,/could not be confirmed/);
          await poll();await $('demo-approve').onclick();assert.equal($('demo-approve').disabled,true);
          assert.equal(calls.filter(call=>call.url==='/api/demo/approve').length,1);
        """)

    def test_merge_and_recovery_still_require_verified_closure(self):
        state=self.approval_state();state['demo']['phase']='merging'
        state['demo']['approval']={'state':'approved','approvedBy':7,'approvedAt':1000,'expiresAt':1900}
        self.run_ui(state,r"""
          assert.equal($('demo-phase').textContent,'Kagent merging approved fix');
          assert.equal($('demo-approve').disabled,true);assert.equal($('demo-phase').className.includes('verified'),false);
          state.demo.phase='reconciling';render();assert.equal($('demo-phase').textContent,'GitOps restoring application');
          assert.match($('demo-human').textContent,/Waiting for GitOps and the application/);
          state.demo.phase='closed';state.demo.ticket={state:'closed',closedVerified:false};render();
          assert.equal($('demo-phase').className.includes('verified'),false);
          state.demo.ticket.closedVerified=true;render();
          assert.equal($('demo-phase').textContent,'Resolved · recovery verified');
          assert.equal($('demo-ticket-state').textContent,'Resolved · recovery verified');
          assert.equal(calls.filter(call=>call.options?.method==='POST').length,0);
        """)

if __name__ == '__main__':
    unittest.main()
