#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BUNDLE_ROOT}"

echo "== Kagent triage v2 KB GitLab MCP work-agent bundle verifier =="
echo "bundle: ${BUNDLE_ROOT}"
echo "mode: local/static; no GitLab, cluster, or querydoc calls"

python3 - <<'PY'
from pathlib import Path
import re
import yaml

root = Path(".")

required = [
    "FRONT-SHEET.md",
    "WORK-AGENT-START-PROMPT.md",
    "CHECKLIST.md",
    "evidence/EVIDENCE-TEMPLATE.md",
    "payload/docs/platform-kb/INDEX.md",
    "payload/docs/platform-kb/agents/kagent-triage-v2-overview.md",
    "payload/docs/platform-kb/agents/gitlab-mcp-kb-update-loop.md",
    "payload/docs/platform-kb/agents/querydoc-knowledge-agent.md",
    "payload/docs/platform-kb/agents/triage-agent-kb-lookup.md",
    "prompts/01-create-kb-docs-via-gitlab-mcp.md",
    "prompts/02-reindex-and-querydoc-proof.md",
    "prompts/03-triage-agent-kb-lookup.md",
    "requests/kb-update-request.yaml",
    "expected/platform-kb-author-agent.yaml",
    "expected/kb-update-evidence-contract.yaml",
    "expected/platform-knowledge-agent-query-contract.yaml",
]

for rel in required:
    path = root / rel
    if not path.exists():
        raise SystemExit(f"MISSING {rel}")
    print(f"FOUND {rel}")

index = (root / "payload/docs/platform-kb/INDEX.md").read_text(encoding="utf-8")
target_paths = [
    "docs/platform-kb/agents/kagent-triage-v2-overview.md",
    "docs/platform-kb/agents/gitlab-mcp-kb-update-loop.md",
    "docs/platform-kb/agents/querydoc-knowledge-agent.md",
    "docs/platform-kb/agents/triage-agent-kb-lookup.md",
]
for target in target_paths:
    if target not in index:
        raise SystemExit(f"INDEX_MISSING_TARGET {target}")
print("INDEX_TARGETS_OK: yes")

for rel in target_paths:
    payload_rel = "payload/" + rel
    text = (root / payload_rel).read_text(encoding="utf-8")
    if not text.startswith("# "):
        raise SystemExit(f"KB_DOC_MISSING_TITLE {payload_rel}")
    print(f"KB_DOC_OK {payload_rel}")

yaml_paths = sorted((root / "requests").glob("*.yaml")) + sorted((root / "expected").glob("*.yaml"))
for path in yaml_paths:
    docs = [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]
    if not docs:
        raise SystemExit(f"EMPTY_YAML {path}")
    for doc in docs:
        print(f"YAML_OK {path} {doc.get('kind')}/{doc.get('metadata', {}).get('name')}")

contract = yaml.safe_load((root / "expected/kb-update-evidence-contract.yaml").read_text(encoding="utf-8"))
markers = contract.get("spec", {}).get("requiredMarkers", [])
for marker in [
    "KAGENT_MCP: called",
    "GITLAB_BRANCH: created",
    "GITLAB_FILE: created_or_updated",
    "KB_INDEX_UPDATED: yes",
    "GITLAB_MR: created",
    "GITLAB_MR_NOTE: created",
    "QUERYDOC_REINDEXED: yes",
    "KB_CITED_HIT: yes",
    "NO_RELEVANT_DOCS: yes",
    "TRIAGE_KB_LOOKUP: called",
    "KB_CITATION_USED_IN_TRIAGE: yes",
]:
    if marker not in markers:
        raise SystemExit(f"MARKER_MISSING {marker}")
print("EVIDENCE_MARKERS_OK: yes")

agent_docs = list(yaml.safe_load_all((root / "expected/platform-kb-author-agent.yaml").read_text(encoding="utf-8")))
forbidden = {"k8s_delete_resource", "k8s_exec", "delete_resource", "exec", "k8s_execute_command"}
for doc in agent_docs:
    if not doc:
        continue
    kind = doc.get("kind")
    spec = doc.get("spec", {})
    if kind == "Agent":
        for tool in spec.get("declarative", {}).get("tools", []):
            blocked = set(tool.get("mcpServer", {}).get("toolNames", [])) & forbidden
            if blocked:
                raise SystemExit(f"FORBIDDEN_AGENT_TOOL {sorted(blocked)}")
    if kind == "ToolGrant":
        blocked = set(spec.get("allowedToolNames", [])) & forbidden
        if blocked:
            raise SystemExit(f"FORBIDDEN_TOOLGRANT_TOOL {sorted(blocked)}")
print("FORBIDDEN_TOOLS_ABSENT: yes")

leak_pattern = re.compile(
    r"(Bearer\s+[A-Za-z0-9._-]+|token=|password|secret:|"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|"
    r"10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)",
    re.IGNORECASE,
)
hits = []
for path in root.rglob("*"):
    if path.is_file() and path.as_posix() != "scripts/verify-bundle.sh":
        if leak_pattern.search(path.read_text(encoding="utf-8")):
            hits.append(path.as_posix())
if hits:
    raise SystemExit("PUBLIC_SAFETY_HITS " + ", ".join(hits))
print("PUBLIC_SAFE_SCAN_OK: yes")
PY

echo "KB_GITLAB_MCP_WORK_AGENT_BUNDLE_VERIFY: passed"
