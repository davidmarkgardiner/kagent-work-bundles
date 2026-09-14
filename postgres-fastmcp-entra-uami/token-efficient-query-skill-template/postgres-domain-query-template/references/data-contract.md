# Data contract template

Populate this with approved semantic information, not a complete database dump
or generated DDL. Keep one skill focused on one business domain.

## Ownership and scope

- Domain: `{{DOMAIN_NAME}}`
- Data owner: `{{OWNER_ROLE_NOT_PERSON}}`
- Approved data product/view: `{{APPROVED_LOGICAL_SOURCE}}`
- Purpose: `{{QUESTIONS_THIS_DOMAIN_CAN_ANSWER}}`
- Explicitly out of scope: `{{QUESTIONS_OR_DATA_NOT_SUPPORTED}}`
- Freshness/SLA: `{{REFRESH_CADENCE_AND_AS_OF_SEMANTICS}}`
- Default time range, if approved: `{{DEFAULT_TIME_RANGE_OR_NONE}}`

## Grain

State what one row means before listing fields.

- Summary grain: `{{ONE_SUMMARY_ROW_REPRESENTS}}`
- Detail grain, if exposed: `{{ONE_DETAIL_ROW_REPRESENTS_OR_NOT_EXPOSED}}`
- Stable identifier for a single-record lookup: `{{APPROVED_IDENTIFIER_OR_NONE}}`

## Approved dimensions

List only dimensions the tools expose. Do not paste every physical column.

| Logical name | Meaning | Type | Cardinality guidance | Allowed use |
|---|---|---|---|---|
| `{{DIMENSION_1}}` | `{{BUSINESS_MEANING}}` | `{{TYPE}}` | `{{LOW_OR_HIGH}}` | `{{FILTER_GROUP_OR_LOOKUP}}` |
| `{{DIMENSION_2}}` | `{{BUSINESS_MEANING}}` | `{{TYPE}}` | `{{LOW_OR_HIGH}}` | `{{FILTER_GROUP_OR_LOOKUP}}` |

For high-cardinality dimensions, name the bounded lookup tool. Do not include a
large distinct-value list or real sample records in this skill.

## Approved metrics

| Metric | Definition | Unit | Valid dimensions | Null/zero rule |
|---|---|---|---|---|
| `{{METRIC_1}}` | `{{OWNER_APPROVED_DEFINITION}}` | `{{UNIT}}` | `{{DIMENSIONS}}` | `{{RULE}}` |
| `{{METRIC_2}}` | `{{OWNER_APPROVED_DEFINITION}}` | `{{UNIT}}` | `{{DIMENSIONS}}` | `{{RULE}}` |

Document whether counts are rows, distinct entities, snapshots, or events.
Document timezone, inclusive/exclusive date boundaries, fiscal calendar, and
the meaning of missing data wherever those facts affect answers.

## Approved relationships

List logical relationships only when a tool or approved view uses them.

| From | To | Cardinality | Approved join meaning |
|---|---|---|---|
| `{{LOGICAL_ENTITY_A}}` | `{{LOGICAL_ENTITY_B}}` | `{{ONE_TO_MANY_ETC}}` | `{{MEANING}}` |

## Business terms and routing synonyms

| Users may say | Interpret as | Disambiguation rule |
|---|---|---|
| `{{TERM_OR_ACRONYM}}` | `{{METRIC_DIMENSION_OR_FILTER}}` | `{{RULE_OR_NONE}}` |

## Sensitive and expensive fields

- Never return: `{{PROHIBITED_FIELD_CLASSES}}`
- Return only for an exact authorized lookup: `{{RESTRICTED_FIELDS_OR_NONE}}`
- Large text/binary fields excluded from chat: `{{LARGE_FIELDS_OR_NONE}}`
- Unsupported joins/calculations: `{{UNSUPPORTED_OPERATIONS}}`
