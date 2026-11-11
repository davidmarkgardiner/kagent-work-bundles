# On-cluster skill evaluation PoC

For a colleague presentation, open [the interactive HTML demo](DEMO.html) and follow [the five-minute presenter guide](DEMO-GUIDE.md). The demo runs offline and separates the proposed GitLab review loop from recorded cluster proof. Download or clone the bundle and open the HTML in a browser; GitHub displays its source.

For a plain-English walkthrough, start with [Our skill test, explained simply](EXPLAINED-SIMPLY.md).

A self-contained namespaced request controller runs one fixed evaluation Job against a reviewed **legacy kagent 0.7.13** Agent. It checks actual native `skills` and `read_file` tool traces against immutable mounted skill bytes, then checks configured answer terms and a citation. This is an acceptance policy, not a general semantic grader.

The request contains only a pinned `scenarioRef`; platform configuration fixes the namespace, controller URL, scenario allowlist, Agent Pod name/UID, image, command and service account. The separate replay controller remains unchanged. No production credentials are included.

Start with [WORK-AGENT-START-HERE.md](WORK-AGENT-START-HERE.md). Read [DESIGN.md](DESIGN.md) for launch fencing, trust boundaries and failure classification.

## Included

- `contract.py`: closed contracts, code binding and pure evidence verification.
- `eval_controller.py`: standard-library Kubernetes client, launch fence, independent inputs, executor validation and immutable result storage.
- `worker.py`: in-cluster kubeconfig, pinned snapshots and shared A2A helper transport.
- `render.py`, `request.py`: portable installation rendering and read-only scenario pinning.
- `handoff.py`: local GitLab MR prose from a receipt; no GitLab network writes.
- `vendor/`: unchanged reviewed golden runner/checker/schema, content-controller dependency and shared scripts. `vendor-lock.json` verifies exact bytes.
- `fixtures/`: bounded historical public synthetic A2A trace, scenario and skill/reference/license bytes. Test replay is explicitly offline.
- `tests/`, `verify.py`: behavioral checks, vendor integrity, render smoke and public-safety scan.

## Offline verification

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python verify.py
```

The final bundle passes 24 behavioral tests, vendor integrity, installation rendering and the public-safety scan. These checks run offline.

## Live Proxmox proof, 11 November 2026

The [stored proof summary](evidence/proof.json) records real Kubernetes controller, Job, model and native tool execution on Kubernetes 1.31.14 with legacy kagent 0.7.13. A separate PoC agent used the existing MiniMax-M2.7 gateway route and the reviewed AKS documentation skill.

| Request | Observed result |
| --- | --- |
| `positive-final` | `Passed`; native skill loading and complete reference reads satisfied the configured checks. |
| `negative-final` | `Failed`; valid tool evidence, deliberately missing answer term. |
| `wrong-pin-final` | `Error`; rejected before any evaluator Job. |

The controller was stopped while `negative-final` was Running. It resumed the same Job UID and independently judged the saved capture. Both final captures were read back and re-judged independently. Eight RBAC checks and two strict admission/immutability checks passed.

Earlier baseline attempts are retained in the summary. Kimi returned its weekly quota limit; the first MiniMax-agent attempt lacked its own ingress rule. Neither failure was counted as a pass. The original agent, scenario and model configuration were preserved. The lab Git source is a fixture; GitLab authentication and publication were not exercised. Full raw captures remain private in the lab and local evidence directory.

The lab remains installed with one polling controller and the dedicated PoC agent. Evaluation requires a new request; no recurring model calls are scheduled. Read the [work-agent guide](WORK-AGENT-START-HERE.md) before adapting it elsewhere.

Semantic score is always `not_scored`; DeepEval is `not_used`. Native kagent 1.x, live GitLab MR creation and workplace token savings are outside this PoC.
