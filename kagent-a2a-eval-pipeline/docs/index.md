# Assay and Warden

Two checks for kagent agents that work together.

| | When | Question | Where it runs |
|---|---|---|---|
| **Assay** | Before an agent is promoted | Is this agent fit for purpose? | GitLab pipeline |
| **Warden** | Every run, in production | Did this run finish properly? | Between the agent and the ticket |

```text
whisky app falls over → Sentinel alerts → agent investigates (read-only)
   → Warden checks the work → receiver writes the GitLab ticket
```

The agents **diagnose and report; they do not fix**. Assay is the test an agent has to pass before it is allowed into this loop.

Start with `FRONT-SHEET.md` in the bundle root, or go straight to [Run it](run-it.md). What is proven and what is not is on [Evidence and limits](evidence.md).

A newer, separate piece, **Lookout**, gives merge requests a first advisory security review: see [Lookout](lookout.md).
