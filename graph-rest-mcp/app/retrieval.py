import json
import os
import re
from pathlib import Path

import duckdb

from app.models import ContextRequest, ContextResponse, Entity, Relationship, Scope, View


ENVIRONMENTS = {"production": {"production", "prod"}, "development": {"development", "dev"}}
TOPICS = {"graph", "topology", "compliance", "compliant", "noncompliant", "non-compliant", "workload", "workloads", "namespace", "namespaces", "view", "views", "relationship", "relationships", "linked", "links", "policy", "policies", "finding", "findings", "owner", "owners"}
QUESTION_WORDS = set("show tell me list describe explain how what which is are the a an do does can you retrieve get give find for in on of to with related link relationships between source scope metadata context size result results objects at most limit environment environments and or only please about their these those has have by each its compliance-style connect connected connects belong belongs associated assessment assessments comply ownership inventory restricted-pod-security checkout metrics payments platform commerce governance approved_workloads approved_compliance".split())
FORBIDDEN = re.compile(r"\b(select|insert|update|delete|drop|alter|truncate|execute|sql|password|credential|token|secret|export|ignore|instructions|reveal|system prompt)\b|;|--|/\*", re.IGNORECASE)
LIMITATION = "Synthetic metadata only. No SQL execution, live database records, fleet totals or proof of real compliance."


def empty_context(status: str, limitation: str, environments: list[str]) -> ContextResponse:
    return ContextResponse(status=status, entities=[], views=[], relationships=[], context=f"{limitation}\nSource: fixture-v1\nScope: {', '.join(environments) or 'unspecified'}", source="fixture-v1", scope=Scope(environments=environments, groupings=[], result_count=0, complete=False), truncated=False, limitations=[limitation, LIMITATION])


def retrieve(request: ContextRequest, database: Path | None = None) -> ContextResponse:
    words = set(re.findall(r"[a-z]+(?:-[a-z]+)*", request.query.lower()))
    environments = [name for name, aliases in ENVIRONMENTS.items() if words & aliases]
    vocabulary = TOPICS | QUESTION_WORDS | set().union(*ENVIRONMENTS.values())
    if FORBIDDEN.search(request.query) or not words & TOPICS or words - vocabulary:
        return empty_context("unsupported", "This service supports graph metadata questions about namespaces, workloads, compliance, views and relationships only.", environments)
    if len(environments) != 1:
        return empty_context("ambiguous", "Specify exactly one environment: production or development.", environments)
    environment = environments[0]
    database = database or Path(os.getenv("GRAPH_DB_PATH", "data/graph.duckdb"))
    with duckdb.connect(str(database), read_only=True, config={"enable_external_access": "false", "threads": "1", "memory_limit": "64MB"}) as connection:
        rows = connection.execute("SELECT category, payload FROM nodes WHERE environment = ? ORDER BY priority LIMIT ?", [environment, request.context_size + 1]).fetchmany(request.context_size + 1)
        edges = connection.execute("SELECT payload FROM edges WHERE environment = ? ORDER BY payload LIMIT 21", [environment]).fetchmany(21)
    truncated = len(rows) > request.context_size
    rows = rows[:request.context_size]
    entities = [Entity.model_validate(json.loads(payload)) for category, payload in rows if category == "entity"]
    views = [View.model_validate(json.loads(payload)) for category, payload in rows if category == "view"]
    nodes = [*entities, *views]
    ids = {node.id for node in nodes}
    relationships = [Relationship.model_validate(json.loads(row[0])) for row in edges]
    relationships = [edge for edge in relationships if edge.source in ids and edge.target in ids]
    if len(relationships) > 20:
        truncated = True
    relationships = relationships[:20]
    coverage = "PARTIAL" if truncated else "complete within the requested fixture scope"
    summary = [f"Coverage: {coverage}; truncated={str(truncated).lower()}; context_size={request.context_size}.", f"Source fixture-v1. Scope {environment}. Returned {len(nodes)} metadata objects."]
    summary.extend(f"{node.kind} {node.name}: {node.compliance}." for node in entities)
    summary.extend(f"View {view.name} has columns {', '.join(view.columns)}." for view in views)
    summary.extend(f"{edge.source} {edge.relation} {edge.target}." for edge in relationships)
    limitations = [LIMITATION]
    if truncated:
        limitations.append("The graph is truncated by context_size. Missing nodes and edges do not establish absence.")
    return ContextResponse(status="supported", entities=entities, views=views, relationships=relationships, context="\n".join(summary), source="fixture-v1", scope=Scope(environments=[environment], groupings=sorted({node.grouping for node in nodes}), result_count=len(nodes), complete=not truncated), truncated=truncated, limitations=limitations)
