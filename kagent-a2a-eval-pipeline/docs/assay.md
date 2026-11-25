# Assay: evaluate before shipping

A GitLab pipeline sends test questions to real agents through the agentgateway A2A route, records what each agent did and said, and scores
it against a written answer key.

```text
validate (offline, every MR) → smoke (live, one cheap case) → eval (seeded fault + decoy, pass^3, one job per agent) → report (verdict)
```

- **Seeded fault.** A throwaway `eval-*` namespace holds one broken app and one healthy decoy. The agent must find the fault and ignore the decoy.
- **Through the gateway.** No port-forward to kagent. The caller identity and the rate limit are the gateway's.
- **Fail closed.** A model outage, a timeout or a missing run is an *error*, never a pass and never a quality failure.
- **Retries.** A POST is retried only when it provably never reached the agent (connection refused, 429, 503). A timeout or 504 is not retried, because the agent may already be acting.
- **One run per conversation.** Every call gets a unique `contextId`: kagent ties a conversation to the first agent that used it.

Code: `a2a_capture.py` (capture), `score_and_gate.py` (score and verdict), `judge.py` (optional advisory LLM rubric, never gates), `.gitlab-ci.yml`.

## Where Assay sits among the tools

| Tool | Role | Status |
|---|---|---|
| **Promptfoo** (`promptfoo-kubernetes` bundle) | Primary runner and workbench for testing skill and prompt content: quality, routing, baselines | In use. `PROMPTFOO-VS-DEEPEVAL.md` (7 Oct 2026) recommends keeping it as the primary runner |
| **DeepEval** | Optional Python judge of recorded agent traces | Analysed, not adopted; pilot only if its diagnostic metrics improve decisions |
| **The repo's deterministic scorer** (`observability/agent-evals/scripts/score-agent-run.py`) | Pass/fail scoring of a captured run | In use; Assay reuses it unchanged |
| **Assay** (this bundle) | Calls **live agents** over A2A through the gateway, captures the real tool trajectory, scores it, gates a GitLab pipeline | Built here. Fills the gap the others left: none of them called real agents and recorded what they did |

Assay is not a vendor product. It is a small capture-and-gate layer on top of the repo's own scorer and GitLab CI, adapted from the Azure AKS-Skills evals pattern.
