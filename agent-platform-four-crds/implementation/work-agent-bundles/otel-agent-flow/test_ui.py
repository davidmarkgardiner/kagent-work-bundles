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
const context=vm.createContext({document:{getElementById:id=>elements.get(id)||null,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:selectors=>all.filter(e=>selectors.split(',').some(s=>e.className.split(' ').includes(s.trim().slice(1))))},history:{replaceState(){}},location:{hash:''},setTimeout:()=>1,clearTimeout(){},setInterval(){},Date,console,assert,elements,calls,root,
  fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>url==='/api/state'?input.state:{revision:0,services:[],logs:[],matching:0,retained:0}};}});
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
