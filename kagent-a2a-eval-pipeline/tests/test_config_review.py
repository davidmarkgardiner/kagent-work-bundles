"""Offline tests for Lookout config review (lookout/config_review, config_review_mcp.py, manifests). No cluster, no network
except a local in-process mock GitLab. The live proof is evidence/LIVE-CONFIG-REVIEW-LAB-2026-11-26.md."""
import copy
import json
import sys
import threading
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOOKOUT = ROOT / "lookout"
sys.path.insert(0, str(LOOKOUT))
sys.path.insert(0, str(LOOKOUT / "lab"))

from config_review import engine as E  # noqa: E402
from config_review import sandbox as S  # noqa: E402
import config_review_mcp as M  # noqa: E402

FX = json.loads((LOOKOUT / "config_review/fixtures/platform-config-mrs.json").read_text())
NS = "lookout-mr-1-abcdef1-0000-a"


def objs(files):
    return [d for p, t in files.items() for d in E.parse_docs(t, p)]


def mr(n):
    m = FX["mrs"][str(n)]
    return objs({p: FX["main"][p] for p in m["files"] if p in FX["main"]}), objs(m["files"])


def sb():
    s = E.Sandboxer(NS, NS + E.GROUP_SUFFIX)
    s.rgd_ns = "classic-agents"
    return s


def agent_v1a3(tools, name="a", ns="kagent", byo=False):
    a = {"apiVersion": "api.kagent.dev/v1alpha3", "kind": "Agent", "metadata": {"name": name, "namespace": ns},
         "spec": {"template": {"inline": {"modelConfig": {"name": "m"}, "tools": [{"mcp": {"server": {"kind": "RemoteMCPServer", "name": "t"}, "tools": tools}}]}}}}
    if byo:
        a["spec"]["type"] = "BYO"
    return a


def policy(expr, name="p", route="r", ns="classic-agents"):
    return {"apiVersion": "agentgateway.dev/v1alpha1", "kind": "AgentgatewayPolicy", "metadata": {"name": name, "namespace": ns},
            "spec": {"targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": route}],
                     "traffic": {"authorization": {"action": "Require", "policy": {"matchExpressions": [expr]}},
                                 "jwtAuthentication": {"mode": "Strict", "providers": [{"audiences": ["aud-x"], "issuer": "https://issuer.example",
                                                                                         "jwks": {"inline": "{\"keys\":[]}"}}]}}}}


class StaticFindings(unittest.TestCase):
    def rules(self, base, head):
        return {(f["severity"], f["rule"]) for f in E.static_findings(base, head)}

    def test_fixture_mrs(self):
        self.assertEqual(self.rules(*mr(21)), set())
        self.assertEqual(self.rules(*mr(22)), {("high", "agent-write-tools"), ("medium", "auth-loosened")})
        self.assertIn(("high", "kro-resource-removed"), self.rules(*mr(23)))
        self.assertIn(("high", "kro-resource-removed"), self.rules(*mr(24)))

    def test_write_tools_both_shapes_and_all_tools(self):
        v1a2 = {"apiVersion": "kagent.dev/v1alpha2", "kind": "Agent", "metadata": {"name": "a", "namespace": "n"},
                "spec": {"declarative": {"tools": [{"mcpServer": {"name": "t", "toolNames": ["k8s_get_resources"]}}]}}}
        v1a2_after = copy.deepcopy(v1a2)
        v1a2_after["spec"]["declarative"]["tools"][0]["mcpServer"]["toolNames"].append("k8s_apply_manifest")
        self.assertIn(("high", "agent-write-tools"), self.rules([v1a2], [v1a2_after]))
        # an omitted tool list means every tool of the server: treated as write tools
        self.assertIn(("high", "agent-write-tools"), self.rules([agent_v1a3(["k8s_get_resources"])], [agent_v1a3([])]))
        self.assertEqual(self.rules([agent_v1a3(["k8s_get_resources"])], [agent_v1a3(["k8s_get_resources", "k8s_get_events"])]), set())

    def test_byo_and_auth_removed_and_deleted(self):
        self.assertIn(("high", "byo-image"), self.rules([], [agent_v1a3([], byo=True)]))
        removed = policy('jwt.sub == "system:serviceaccount:classic-agents:c"')
        after = copy.deepcopy(removed)
        after["spec"]["traffic"].pop("authorization")
        self.assertIn(("high", "auth-removed"), self.rules([removed], [after]))
        self.assertIn(("medium", "deleted"), self.rules([removed], []))


class SandboxCopy(unittest.TestCase):
    def test_refusals(self):
        bad = [
            {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "s", "namespace": "x"}},
            {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "ClusterRoleBinding", "metadata": {"name": "c"}},
            {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": {"name": "n", "namespace": "x"},
             "spec": {"egress": [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}]}},
            agent_v1a3([], name="byo", byo=True),
            {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": "j", "namespace": "x"}, "spec": {}},
        ]
        xns = agent_v1a3(["k8s_get_resources"], name="xns")
        xns["spec"]["template"]["inline"]["tools"][0]["mcp"]["server"]["namespace"] = "kagent-system"
        bad.append(xns)
        s = sb()
        self.assertEqual(s.prepare(bad), [])
        self.assertEqual(len(s.refused), len(bad), s.refused)

    def test_rgd_template_escapes_refused(self):
        rgd = mr(23)[1][0]
        for mutate, why in [
            (lambda r: r["spec"]["resources"][0]["template"]["metadata"].__setitem__("namespace", "default"), "namespace"),
            (lambda r: r["spec"]["resources"].append({"id": "crb", "template": {"apiVersion": "rbac.authorization.k8s.io/v1",
                                                                                 "kind": "ClusterRoleBinding", "metadata": {"name": "x"}}}), "never creates"),
            (lambda r: r["spec"]["resources"].append({"id": "ext", "externalRef": {"kind": "Secret"}}), "not a template"),
        ]:
            r = copy.deepcopy(rgd)
            mutate(r)
            s = sb()
            self.assertEqual(s.prepare([r]), [])
            self.assertIn(why, s.refused[0])

    def test_rewrites_route_policy_and_auth_fields(self):
        base, head = mr(21)
        s = sb()
        out = {o["kind"]: o for o in s.prepare(head)}
        route, pol = out["HTTPRoute"], out["AgentgatewayPolicy"]
        self.assertEqual(route["metadata"]["namespace"], NS)
        self.assertEqual(route["spec"]["parentRefs"][0]["name"], "lookout-gw")
        self.assertNotIn("namespace", route["spec"]["parentRefs"][0])
        self.assertEqual(route["spec"]["rules"][0]["backendRefs"][0]["name"], "lookout-echo")
        orig = [o for o in head if o["kind"] == "AgentgatewayPolicy"][0]
        # only the subject's namespace part changes; issuer, audience and JWKS are exactly as in the MR
        self.assertEqual(pol["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"],
                         [f'jwt.sub == "system:serviceaccount:{NS}:demo-caller"'])
        self.assertEqual(pol["spec"]["traffic"]["jwtAuthentication"], orig["spec"]["traffic"]["jwtAuthentication"])
        self.assertTrue(any("not tested" in r for r in s.rewrites))

    def test_subject_in_other_namespace_not_rewritten(self):
        s = sb()
        out = s.prepare([policy('jwt.sub == "system:serviceaccount:other-team:c"')])
        self.assertIn("system:serviceaccount:other-team:c", json.dumps(out))

    def test_kro_rgd_group_job_and_readiness(self):
        s = sb()
        rgd = s.prepare(mr(23)[1])[0]
        self.assertEqual(rgd["spec"]["schema"]["group"], NS + E.GROUP_SUFFIX)
        self.assertEqual(rgd["spec"]["schema"]["kind"], "ClassicSecureAgent")
        self.assertTrue(rgd["metadata"]["name"].startswith(NS))
        res = {r["id"]: r for r in rgd["spec"]["resources"]}
        job = res["golden"]["template"]["spec"]["template"]["spec"]
        self.assertEqual(job["containers"][0]["image"], "python:3.12-alpine")
        self.assertEqual(job["containers"][0]["command"], ["true"])
        self.assertFalse(any("projected" in v for v in job["volumes"]))
        self.assertFalse(job["automountServiceAccountToken"])
        self.assertNotIn("readyWhen", res["agent"])
        self.assertIn("readyWhen", res["golden"])
        for r in res.values():
            self.assertEqual(r["template"]["metadata"]["namespace"], "${schema.metadata.namespace}")
        self.assertIn(f"system:serviceaccount:{NS}:", json.dumps(rgd))
        self.assertNotIn("system:serviceaccount:classic-agents:", json.dumps(rgd))

    def test_service_type_and_backend(self):
        s = sb()
        out = s.prepare([{"apiVersion": "v1", "kind": "Service", "metadata": {"name": "lb", "namespace": "x"}, "spec": {"type": "LoadBalancer"}},
                         {"apiVersion": "agentgateway.dev/v1alpha1", "kind": "AgentgatewayBackend", "metadata": {"name": "b", "namespace": "x"},
                          "spec": {"static": {"host": "169.254.169.254", "port": 80}}}])
        self.assertEqual(out[0]["spec"]["type"], "ClusterIP")
        self.assertIn("lookout-echo", out[1]["spec"]["static"]["host"])

    def test_helm_template_refused(self):
        with self.assertRaises(E.Refused):
            E.parse_docs("kind: ConfigMap\nmetadata: {name: '{{ .Values.x }}'}\n", "chart/templates/cm.yaml")


class ProbeDiff(unittest.TestCase):
    def rules(self, before, after):
        return {(f["severity"], f["rule"]) for f in E.diff_matrix(before, after)}

    def test_matrix(self):
        b = {"r": {"anonymous": 401, "caller": 200, "lookout-stranger": 403}}
        self.assertEqual(self.rules(b, copy.deepcopy(b)), set())
        self.assertIn(("high", "route-opened"), self.rules(b, {"r": {"anonymous": 200, "caller": 200, "lookout-stranger": 403}}))
        self.assertIn(("high", "route-opened"), self.rules(b, {"r": {"anonymous": 401, "caller": 200, "lookout-stranger": 404}}))
        self.assertIn(("medium", "reach-removed"), self.rules(b, {"r": {"anonymous": 401, "caller": 403, "lookout-stranger": 403}}))
        self.assertIn(("high", "route-broken"), self.rules(b, {"r": {"anonymous": 401, "caller": 503, "lookout-stranger": 403}}))
        self.assertIn(("medium", "route-removed"), self.rules(b, {}))
        self.assertIn(("high", "route-opened"), self.rules({}, {"new": {"anonymous": 200}}))
        self.assertEqual(self.rules({}, {"new": {"anonymous": 401, "lookout-stranger": 403}}), set())

    def test_numbering(self):
        f = E.number([E._f("info", "x", "c", "s", []), E._f("high", "y", "a", "s", []), E._f("medium", "z", "b", "s", [])])
        self.assertEqual([(x["id"], x["severity"]) for x in f], [("CR-1", "high"), ("CR-2", "medium"), ("CR-3", "info")])


class FetchFromMockGitLab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import mock_gitlab
        cls.srv = mock_gitlab.serve(0)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        import gitlab_review_mcp as g
        cls.api = staticmethod(g.make_api(f"http://127.0.0.1:{cls.srv.server_address[1]}", "x"))

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_fetch_and_head_moved(self):
        got = S.fetch_mr(self.api, "lab/platform-config", 22, "22" * 20)
        self.assertEqual(len(got["base"]), 3)
        self.assertEqual(len(got["head"]), 3)
        self.assertEqual(S.fetch_mr(self.api, "lab/platform-config", 21, "21" * 20)["files"][0]["new"], True)
        with self.assertRaises(ValueError):
            S.fetch_mr(self.api, "lab/platform-config", 22, "ab" * 20)

    def test_post_note_gate(self):
        tools = M.ConfigReviewTools(self.api, ["lab/platform-config"], kube=object())
        sha = "22" * 20
        with self.assertRaises(ValueError):                         # no review run yet
            tools.post_note("lab/platform-config", 22, sha, "fine")
        tools.cache[("lab/platform-config", 22, sha)] = {"findings": [{"id": "CR-1", "severity": "high"},
                                                                      {"id": "CR-2", "severity": "medium"}]}
        with self.assertRaises(ValueError) as ctx:                  # the high finding is not cited
            tools.post_note("lab/platform-config", 22, sha, "Looks fine. CR-2 is minor.")
        self.assertIn("CR-1", str(ctx.exception))
        res = tools.post_note("lab/platform-config", 22, sha, "Needs changes: CR-1 (high).")
        self.assertIn(res["action"], ("created", "updated"))

    def test_repeat_call_returns_same_evidence_and_runs_once(self):
        calls = []
        orig = S.run_review
        S.run_review = lambda *a, **k: calls.append(1) or {"mode": "config", "head_sha": "21" * 20, "findings": [], "summary": {"high": 0, "medium": 0, "info": 0}}
        M.sandbox.run_review = S.run_review
        try:
            tools = M.ConfigReviewTools(self.api, ["lab/platform-config"], kube=object())
            first = tools.config_review("lab/platform-config", 21, "21" * 20)
            second = tools.config_review("lab/platform-config", 21, "21" * 20)
        finally:
            S.run_review = M.sandbox.run_review = orig
        self.assertEqual(len(calls), 1)          # one sandbox run
        self.assertIn("draft_note", first)
        self.assertEqual(first, second)          # full evidence again: a short answer made the live agent think data was missing
        with self.assertRaises(ValueError):
            tools.config_review("someone/else", 21, "21" * 20)


class FakeKube:
    def __init__(self):
        self.calls = []

    def list(self, g, k, ns=None, selector=""):
        return [{"metadata": {"name": "demo"}}] if k == "ClassicSecureAgent" and not any(c[0] == "delete" and c[2] == k for c in self.calls) else []

    def delete(self, g, k, name, ns=None):
        self.calls.append(("delete", g, k, name))

    def clear_finalizers(self, *a):
        self.calls.append(("clear",) + a)


class Teardown(unittest.TestCase):
    def test_instance_before_rgd_before_crd_and_namespace(self):
        side = S.Side.__new__(S.Side)
        side.kube, side.ns, side.notes = FakeKube(), NS, []
        side.objs = [sb().prepare(mr(23)[1])[0]]
        S.Kube.register(NS + E.GROUP_SUFFIX, "ClassicSecureAgent", "v1alpha1", "classicsecureagents")
        side.teardown()
        kinds = [c[2] for c in side.kube.calls if c[0] == "delete"]
        self.assertEqual(kinds, ["ClassicSecureAgent", "ResourceGraphDefinition", "CustomResourceDefinition", "Namespace"])
        self.assertTrue(side.kube.calls[2][3].endswith(E.GROUP_SUFFIX))


class Manifests(unittest.TestCase):
    def docs(self):
        text = (LOOKOUT / "manifests/config-review-sandbox.yaml").read_text().replace("{{INSTANCE_PLURALS}}", "classicsecureagents")
        return {(d["kind"], d["metadata"]["name"]): d for d in yaml.safe_load_all(text)}

    def test_admission_fences(self):
        d = self.docs()
        scope = d[("ValidatingAdmissionPolicy", "lookout-config-review-scope")]["spec"]
        self.assertEqual(scope["failurePolicy"], "Fail")
        self.assertEqual(scope["matchConstraints"]["resourceRules"][0]["resources"], ["*/*"])    # subresources too (tokens)
        rules = " ".join(v["expression"] for v in scope["validations"])
        for needle in ('startsWith("lookout-mr-")', '.lookout.sandbox', "request.dryRun == true"):
            self.assertIn(needle, rules)
        kids = d[("ValidatingAdmissionPolicy", "lookout-kro-children-scope")]["spec"]
        self.assertIn("kro.run/instance-group", kids["matchConditions"][0]["expression"])
        for name in ("lookout-config-review-scope", "lookout-kro-children-scope"):
            self.assertEqual(d[("ValidatingAdmissionPolicyBinding", name)]["spec"]["validationActions"], ["Deny"])

    def test_rbac_has_no_secrets_or_rbac_or_wildcard_resources(self):
        role = self.docs()[("ClusterRole", "lookout-config-review")]
        for rule in role["rules"]:
            self.assertNotIn("secrets", rule["resources"])
            self.assertNotIn("*", rule["resources"])
            self.assertNotIn("*", rule["verbs"])
            self.assertNotIn("rbac.authorization.k8s.io", rule["apiGroups"])

    def test_configmap_items_match_deploy_script(self):
        dep = self.docs()[("Deployment", "lookout-config-review-mcp")]
        keys = {i["key"] for v in dep["spec"]["template"]["spec"]["volumes"] if "configMap" in v for i in v["configMap"]["items"]}
        script = (LOOKOUT / "lab/deploy-config-review.sh").read_text()
        for k in keys:
            self.assertIn(f"--from-file={k}=", script)

    def test_agent_has_only_three_tools(self):
        a = yaml.safe_load((LOOKOUT / "manifests/mr-config-review-agent-v1alpha3.yaml").read_text())
        tools = a["spec"]["template"]["inline"]["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(set(tools[0]["mcp"]["tools"]), M_TOOLS)


M_TOOLS = {t["name"] for t in M.TOOLS}


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------- regression tests for the 2026-11-26 code review

import base64 as _b64  # noqa: E402
import http.server as _hs  # noqa: E402
from config_review import janitor as J  # noqa: E402
from config_review.kube import KubeError as _KE  # noqa: E402


class ReviewFindings(unittest.TestCase):
    def test_1_kro_agent_becomes_stand_in_and_status_reads_refused(self):
        s = sb()
        rgd = s.prepare(mr(23)[1])[0]
        agent = {r["id"]: r for r in rgd["spec"]["resources"]}["agent"]["template"]
        self.assertEqual((agent["apiVersion"], agent["kind"]), ("v1", "ConfigMap"))
        self.assertEqual(agent["metadata"]["labels"], {"lookout.dev/stand-in": "Agent"})
        self.assertNotIn("Agent", {r["template"]["kind"] for r in rgd["spec"]["resources"]})
        reads = copy.deepcopy(mr(23)[1][0])
        reads["spec"]["schema"]["status"]["ready"] = "${agent.status.conditions}"
        s2 = sb()
        self.assertEqual(s2.prepare([reads]), [])
        self.assertIn("spec or status", s2.refused[0])
        kids = yaml.safe_load_all((LOOKOUT / "manifests/config-review-sandbox.yaml").read_text().replace("{{INSTANCE_PLURALS}}", "x"))
        vap = [d for d in kids if d["kind"] == "ValidatingAdmissionPolicy" and d["metadata"]["name"] == "lookout-kro-children-scope"][0]
        rules = " ".join(v["expression"] for v in vap["spec"]["validations"])
        self.assertIn('"kagent.dev", "api.kagent.dev"', rules)
        self.assertIn('"Pod", "Deployment"', rules)

    def test_2_live_rgd_never_shadows_the_mrs_rgd(self):
        live = mr(23)[0][0]
        class K:
            def list(self, g, k, ns=None, selector=""):
                return [copy.deepcopy(live)] if k == "ResourceGraphDefinition" else []
        inst = {"apiVersion": "demo.kagent.dev/v1alpha1", "kind": "ClassicSecureAgent", "metadata": {"name": "demo", "namespace": "classic-agents"}, "spec": {}}
        self.assertEqual(S._live_rgds_for_instances(K(), mr(23)[1] + [inst]), [])   # the MR defines the kind: no live copy
        self.assertEqual(len(S._live_rgds_for_instances(K(), [inst])), 1)            # instance-only MR: live RGD used

    def test_3_deleted_or_namespaceless_policies_are_not_resurrected(self):
        live = policy('jwt.sub == "system:serviceaccount:classic-agents:c"', name="listener", ns="classic-agents")
        self.assertEqual(S._not_overridden([live], [copy.deepcopy(live)]), [])         # in base (deleted in head): not context
        no_ns = copy.deepcopy(live); no_ns["metadata"].pop("namespace")
        self.assertEqual(S._not_overridden([live], [no_ns]), [])                       # MR object without namespace matches
        other = policy("x", name="other")
        self.assertEqual(S._not_overridden([live, other], [no_ns]), [other])

    def test_4_non_gateway_parent_refs_never_keep_a_namespace(self):
        route = {"apiVersion": "gateway.networking.k8s.io/v1", "kind": "HTTPRoute", "metadata": {"name": "r", "namespace": "x"},
                 "spec": {"parentRefs": [{"kind": "Service", "name": "kagent-controller", "namespace": "kagent"},
                                         {"name": "gw", "namespace": "shared", "sectionName": "http"}],
                          "rules": [{"backendRefs": [{"name": "b", "port": 80}]}]}}
        out = sb().prepare([route])[0]
        self.assertEqual(out["spec"]["parentRefs"], [{"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": "lookout-gw", "sectionName": "http"}])
        self.assertNotIn("kagent", json.dumps(out["spec"]))

    def test_5_service_keeps_only_selector_ports_clusterip(self):
        svc = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "s", "namespace": "x"},
               "spec": {"type": "${schema.spec.svcType}", "externalIPs": ["1.2.3.4"], "loadBalancerIP": "1.2.3.4",
                        "selector": {"a": "b"}, "ports": [{"port": 80}]}}
        out = sb().prepare([svc])[0]
        self.assertEqual(out["spec"], {"selector": {"a": "b"}, "ports": [{"port": 80}], "type": "ClusterIP"})

    def test_8_policy_backends_and_remote_jwks_fenced(self):
        p = policy('jwt.sub == "x"')
        p["spec"]["traffic"]["extAuth"] = {"backendRef": {"name": "authz", "namespace": "classic-agents", "port": 9000}}
        out = sb().prepare([p])[0]
        self.assertEqual(out["spec"]["traffic"]["extAuth"]["backendRef"]["name"], "lookout-echo")
        remote = policy('jwt.sub == "x"'); remote["spec"]["traffic"]["jwtAuthentication"]["providers"][0]["jwks"] = {"remote": {"url": "http://169.254.169.254/"}}
        s = sb(); self.assertEqual(s.prepare([remote]), []); self.assertIn("remote JWKS", s.refused[0])
        cross = policy('jwt.sub == "x"'); cross["spec"]["traffic"]["extAuth"] = {"backendRef": {"name": "a", "namespace": "kube-system"}}
        s = sb(); self.assertEqual(s.prepare([cross]), []); self.assertIn("kube-system", s.refused[0])

    def test_9_cel_lists_and_bad_yaml_do_not_crash(self):
        route = {"apiVersion": "gateway.networking.k8s.io/v1", "kind": "HTTPRoute", "metadata": {"name": "r", "namespace": "x"},
                 "spec": {"parentRefs": [{"name": "gw"}], "rules": "${schema.spec.rules}"}}
        s = sb(); self.assertEqual(s.prepare([route]), []); self.assertIn("not a list", s.refused[0])
        s = sb(); self.assertEqual(s.prepare([{"apiVersion": "v1", "kind": "ConfigMap", "metadata": {}}]), [])   # no name: no crash
        files = {"good.yaml": "apiVersion: v1\nkind: ConfigMap\nmetadata: {name: a, namespace: x}\n", "bad.yaml": "kind: [unclosed\n"}
        got = S.fetch_mr(fake_gitlab(files), "g/p", 1, "a" * 40)
        self.assertTrue(got["invalid_yaml"] and "bad.yaml" in got["invalid_yaml"][0])

    def test_10_yaml_filtered_before_the_cap(self):
        files = {f"src/f{i}.py": "x = 1\n" for i in range(60)}
        files["platform/route.yaml"] = "apiVersion: gateway.networking.k8s.io/v1\nkind: HTTPRoute\nmetadata: {name: r, namespace: x}\n"
        got = S.fetch_mr(fake_gitlab(files), "g/p", 1, "a" * 40)
        self.assertEqual([f["path"] for f in got["files"]], ["platform/route.yaml"])
        self.assertFalse(got["incomplete"])

    def test_11_teardown_continues_after_a_failed_step(self):
        class K(FakeKube):
            def delete(self, g, k, name, ns=None):
                super().delete(g, k, name, ns)
                if k == "ResourceGraphDefinition":
                    raise _KE(500, "boom")
        side = S.Side.__new__(S.Side)
        side.kube, side.ns, side.notes = K(), NS, []
        side.objs = [sb().prepare(mr(23)[1])[0]]
        S.Kube.register(NS + E.GROUP_SUFFIX, "ClassicSecureAgent", "v1alpha1", "classicsecureagents")
        with self.assertRaises(_KE):
            side.teardown()
        self.assertEqual([c[2] for c in side.kube.calls if c[0] == "delete"][-2:], ["CustomResourceDefinition", "Namespace"])

    def test_12_plural_comes_from_the_crd(self):
        class K:
            def list(self, g, k, ns=None, selector=""):
                return [{"spec": {"group": "x.lookout.sandbox", "names": {"kind": "NetPolicy", "plural": "netpolicies"}}}]
        self.assertEqual(S._plural(K(), "x.lookout.sandbox", "NetPolicy"), "netpolicies")

    def test_13_rbac_403_on_a_new_kind_is_not_tested_not_rejected(self):
        side = S.Side.__new__(S.Side)
        side.apply_errors, side.notes, side.untested = [], [], []
        class K:
            def apply(self, o, dry_run=False):
                raise _KE(403, 'thing "x" is forbidden: User "system:serviceaccount:kagent:lookout-config-review" cannot create resource')
        side.kube = K()
        side._apply({"apiVersion": "a.lookout.sandbox/v1", "kind": "NewKind", "metadata": {"name": "x", "namespace": NS}})
        self.assertEqual(side.apply_errors, [])
        self.assertIn("not tested", side.notes[0])

    def test_16_new_open_route_reported_once(self):
        f = E.diff_matrix({}, {"new": {"anonymous": 200, E.STRANGER: 200}})
        self.assertEqual(sum(1 for x in f if x["rule"] == "route-opened" and "anonymous" in x["title"]), 1)

    def test_17_template_kro_labels_stripped(self):
        r = copy.deepcopy(mr(23)[1][0])
        r["spec"]["resources"][0]["template"]["metadata"]["labels"] = {"kro.run/instance-group": "fake", "app": "a"}
        out = sb().prepare([r])[0]
        self.assertEqual(out["spec"]["resources"][0]["template"]["metadata"]["labels"], {"app": "a"})


def fake_gitlab(files: dict):
    def api(method, path, payload=None):
        if path.endswith("/merge_requests/1"):
            return {"sha": "a" * 40, "diff_refs": {"base_sha": "b" * 40}}
        if "/diffs" in path:
            page = int(path.split("page=")[-1])
            items = [{"new_path": p, "old_path": p, "new_file": True} for p in files]
            return items[(page - 1) * 100: page * 100]
        if "/repository/files/" in path:
            name = urllib_unquote(path.split("/repository/files/")[1].split("?")[0])
            return {"content": _b64.b64encode(files[name].encode()).decode()}
        raise AssertionError(path)
    return api


def urllib_unquote(s):
    import urllib.parse
    return urllib.parse.unquote(s)


class _Probe(_hs.BaseHTTPRequestHandler):
    hits = []
    def do_GET(self):
        _Probe.hits.append((self.path, self.headers.get("Host"), self.headers.get("X-Team")))
        if self.path == "/redir":
            self.send_response(302); self.send_header("Location", "http://127.0.0.1:1/steal"); self.end_headers()
        elif self.path == "/gw404":
            self.send_response(404); self.end_headers()
        elif self.path == "/echo404":
            self.send_response(404); self.send_header(S.ECHO_MARKER, "1"); self.end_headers()
        else:
            self.send_response(200); self.end_headers()
    def log_message(self, *a):
        pass


class Probes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _hs.ThreadingHTTPServer(("127.0.0.1", 0), _Probe)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_6_redirects_not_followed(self):
        _Probe.hits.clear()
        self.assertEqual(S._http(self.base + "/redir", "tok"), 302)
        self.assertEqual(len(_Probe.hits), 1)

    def test_7_gateway_404_is_no_match_echo_404_is_reached(self):
        self.assertEqual(S._http(self.base + "/gw404", None), E.NO_MATCH)
        self.assertEqual(E.classify(E.NO_MATCH), "no-match")
        self.assertEqual(S._http(self.base + "/echo404", None), 404)
        route = {"spec": {"hostnames": ["*.agents.example"], "rules": [{"matches": [{"path": {"value": "/a"}, "method": "GET",
                                                                                      "headers": [{"name": "X-Team", "value": "blue"}]}]}]}}
        path, host, method, hdrs = S._probe_target(route)
        _Probe.hits.clear()
        S._http(self.base + path, None, host, method, hdrs)
        self.assertEqual(_Probe.hits[0], ("/a", "probe.agents.example", "blue"))
        f = E.diff_matrix({"r": {"anonymous": 401}}, {"r": {"anonymous": E.NO_MATCH}})
        self.assertIn("probe-no-match", {x["rule"] for x in f})


class Janitor(unittest.TestCase):
    def test_expired_namespace_removed_young_kept(self):
        now = 2_000_000_000
        class K:
            deleted = []
            def list(self, g, k, ns=None, selector=""):
                if k == "Namespace":
                    return [{"metadata": {"name": "lookout-mr-1-a", "labels": {"lookout.dev/expires": str(now - 10)}, "creationTimestamp": "2026-11-26T10:00:00Z"}},
                            {"metadata": {"name": "lookout-mr-2-a", "labels": {"lookout.dev/expires": str(now + 999)}}}]
                return []
            def delete(self, g, k, name, ns=None):
                K.deleted.append((k, name))
        out = J.sweep(K(), now=now, log=lambda *_: None)
        self.assertEqual(out["namespaces"], ["lookout-mr-1-a"])
        self.assertNotIn(("Namespace", "lookout-mr-2-a"), K.deleted)


class ReReviewFindings(unittest.TestCase):
    """Regression tests for the re-review (issues A, B and items 9, 10)."""

    def test_A_refused_objects_recorded_and_policy_routes(self):
        p = policy('jwt.sub == "x"', route="guarded")
        p["spec"]["traffic"]["jwtAuthentication"]["providers"][0]["jwks"] = {"remote": {"url": "https://issuer.example/keys"}}
        s = sb()
        self.assertEqual(s.prepare([p]), [])
        self.assertEqual([E.key(o) for o in s.refused_objs], [E.key(p)])
        self.assertEqual(E.policy_routes(p), {"guarded"})
        gw = policy("x"); gw["spec"]["targetRefs"] = [{"kind": "Gateway", "name": "g"}]
        self.assertIsNone(E.policy_routes(gw))
        f = E.diff_matrix({"guarded": {"anonymous": 401}}, {"guarded": {"anonymous": 200}})
        self.assertEqual(f[0]["route"], "guarded")

    def test_B_janitor_survives_an_unreadable_kind(self):
        class K:
            def list(self, g, k, ns=None, selector=""):
                if k == "CustomResourceDefinition":
                    return [{"metadata": {"name": "xs.a.lookout.sandbox", "creationTimestamp": "2020-01-01T00:00:00Z"},
                             "spec": {"group": "a.lookout.sandbox", "names": {"kind": "X", "plural": "xs"}, "versions": [{"name": "v1", "served": True}]}}]
                if k == "X":
                    raise _KE(403, "forbidden")
                if k == "Namespace":
                    return [{"metadata": {"name": "lookout-mr-9-a", "labels": {"lookout.dev/expires": "1"}}}]
                return []
            def delete(self, g, k, name, ns=None):
                pass
        out = J.sweep(K(), now=2_000_000_000, log=lambda *_: None)
        self.assertEqual(out["namespaces"], ["lookout-mr-9-a"])
        self.assertEqual(out["crds"], ["xs.a.lookout.sandbox"])
        self.assertTrue(out["errors"])

    def test_9_any_crash_after_fetch_still_returns_a_note(self):
        class Boom:
            def list(self, *a, **k):
                raise RuntimeError("cluster unreachable")
            def get(self, *a, **k):
                raise RuntimeError("cluster unreachable")
        files = {"r.yaml": "apiVersion: gateway.networking.k8s.io/v1\nkind: HTTPRoute\nmetadata: {name: r, namespace: x}\n"}
        ev = S.run_review(Boom(), fake_gitlab(files), "g/p", 1, "a" * 40)
        self.assertEqual(ev["findings"][0]["rule"], "review-incomplete")
        self.assertIn("NOT tested", S.draft_note(ev) + ev["findings"][0]["title"])

    def test_10_incomplete_is_not_worded_as_no_change(self):
        self.assertIn("incomplete", S.draft_note({"mode": "incomplete"}).lower())
        self.assertNotIn("No kagent", S.draft_note({"mode": "incomplete"}))

    def test_service_nodeport_stripped(self):
        out = sb().prepare([{"apiVersion": "v1", "kind": "Service", "metadata": {"name": "s", "namespace": "x"},
                             "spec": {"type": "NodePort", "ports": [{"port": 80, "nodePort": 30080}]}}])[0]
        self.assertEqual(out["spec"]["ports"], [{"port": 80}])


class ApprovalLowNotes(unittest.TestCase):
    def test_target_selectors_mean_every_route(self):
        p = policy("x"); p["spec"]["targetSelectors"] = [{"kind": "HTTPRoute", "matchLabels": {"a": "b"}}]
        self.assertIsNone(E.policy_routes(p))

    def test_janitor_bad_expiry_label(self):
        class K:
            def list(self, g, k, ns=None, selector=""):
                return [{"metadata": {"name": "lookout-mr-3-a", "labels": {"lookout.dev/expires": "soon"}}}] if k == "Namespace" else []
            def delete(self, *a):
                pass
        self.assertEqual(J.sweep(K(), now=2_000_000_000, log=lambda *_: None)["namespaces"], ["lookout-mr-3-a"])


class KagentVersions(unittest.TestCase):
    def test_v1alpha2_agent_matches_v1alpha3(self):
        a2 = yaml.safe_load((LOOKOUT / "manifests/mr-config-review-agent.yaml").read_text())
        a3 = yaml.safe_load((LOOKOUT / "manifests/mr-config-review-agent-v1alpha3.yaml").read_text())
        self.assertEqual(a2["apiVersion"], "kagent.dev/v1alpha2")
        self.assertEqual(a2["spec"]["declarative"]["systemMessage"], a3["spec"]["template"]["inline"]["systemPrompt"])
        self.assertEqual(a2["spec"]["declarative"]["tools"][0]["mcpServer"]["toolNames"], a3["spec"]["template"]["inline"]["tools"][0]["mcp"]["tools"])

    def test_v1alpha2_agent_valid_against_0_9_12_schema(self):
        sys.path.insert(0, str(ROOT / "tests"))
        import test_demo_kagent09 as k09
        doc = yaml.safe_load((LOOKOUT / "manifests/mr-config-review-agent.yaml").read_text().replace("{{MODEL_CONFIG}}", "m"))
        self.assertEqual(k09.check_0_9(doc), [])
