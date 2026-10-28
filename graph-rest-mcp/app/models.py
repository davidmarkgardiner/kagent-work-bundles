from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, model_validator


Label = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:/ -]+$")]
Identifier = Annotated[str, StringConstraints(min_length=1, max_length=96, pattern=r"^[a-zA-Z0-9_.:-]+$")]
Query = Annotated[str, StringConstraints(min_length=1, max_length=512, strip_whitespace=True)]
ContextSize = Annotated[StrictInt, Field(ge=1, le=10)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ContextRequest(Contract):
    query: Query
    context_size: ContextSize = 10


class Entity(Contract):
    id: Identifier
    kind: Literal["namespace", "workload", "policy", "finding", "team"]
    name: Label
    environment: Label
    grouping: Label
    compliance: Literal["compliant", "non_compliant", "not_applicable"] = "not_applicable"


class View(Contract):
    id: Identifier
    name: Label
    environment: Label
    grouping: Label
    columns: Annotated[list[Identifier], Field(max_length=8)]


class Relationship(Contract):
    source: Identifier
    target: Identifier
    relation: Literal["contains", "assessed_by", "evaluates", "owned_by", "describes"]


class Scope(Contract):
    environments: Annotated[list[Label], Field(max_length=4)]
    groupings: Annotated[list[Label], Field(max_length=8)]
    result_count: Annotated[StrictInt, Field(ge=0, le=10)]
    complete: bool


class ContextResponse(Contract):
    status: Literal["supported", "unsupported", "ambiguous"]
    entities: Annotated[list[Entity], Field(max_length=10)]
    views: Annotated[list[View], Field(max_length=3)]
    relationships: Annotated[list[Relationship], Field(max_length=20)]
    context: Annotated[str, StringConstraints(max_length=4096)]
    source: Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")]
    scope: Scope
    truncated: bool
    limitations: Annotated[list[Annotated[str, StringConstraints(max_length=256)]], Field(max_length=8)]

    @model_validator(mode="after")
    def graph_is_closed(self):
        nodes = [*self.entities, *self.views]
        ids = {node.id for node in nodes}
        if len(nodes) > 10 or len(ids) != len(nodes) or self.scope.result_count != len(nodes):
            raise ValueError("invalid result count or duplicate identity")
        if any(edge.source not in ids or edge.target not in ids for edge in self.relationships):
            raise ValueError("relationship outside returned graph")
        if self.status != "supported" and (nodes or self.relationships or not self.limitations):
            raise ValueError("unsupported context must be empty and explain its limitation")
        if self.status == "supported" and (self.scope.complete == self.truncated):
            raise ValueError("completeness contradicts truncation")
        if any(node.environment not in self.scope.environments for node in nodes):
            raise ValueError("node outside declared environment scope")
        if any(node.grouping not in self.scope.groupings for node in nodes):
            raise ValueError("node outside declared grouping scope")
        return self
