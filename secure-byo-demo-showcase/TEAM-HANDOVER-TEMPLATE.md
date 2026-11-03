# What we delivered and demonstrated

Fill this report privately from the final revision. Leave unproved rows as **not verified**. Do not present this template as a completed case study.

**Session:** {{DATE_TARGET_NAMESPACE_AND_SOURCE_REVISION}}

**Scope:** no-Substrate agent onboarding, approved JWT identities, existing Agent Gateway and observability services.

**Opening statement after the gates pass:** "We submitted one approved agent YAML. The operator configured its runtime, model, tools, skills, knowledge and secure Gateway connection. Automatic security checks and the GoldenScenario verified the resulting agent. We then watched and invoked that agent using the current request's evidence."

Use that statement only if every associated claim below is proved. Otherwise replace it with the observed partial result and exact missing gates.

| Delivered or observed item | Actual reference and receipt | Verdict |
| --- | --- | --- |
| Owner YAML, editable fields and request UID | {{OWNER_FILE_UID_REVISION}} | Not verified |
| Existing operator/profile and runtime kind | {{DEPLOYMENT_OR_JOB_AND_IMAGE_DIGEST}} | Not verified |
| Bound ModelConfig and actual model call | {{MODEL_REFERENCE_AND_CALL_RECEIPT}} | Not verified |
| Approved MCP binding and actual handler call | {{TOOL_REFERENCE_AND_BACKEND_WITNESS}} | Not verified |
| Skill and knowledge release pins plus real use | {{CONTENT_PINS_AND_LOAD_READ_EVIDENCE}} | Not verified |
| HTTPRoute, ReferenceGrant and attached policies | {{RESOURCE_INVENTORY_AND_CURRENT_CONDITIONS}} | Not verified |
| JWT positive/negative cases and no forbidden dispatch | {{SECURITY_RECEIPTS}} | Not verified |
| Automatically generated/executed GoldenScenario | {{SCENARIO_CURRENT_OWNER_SPEC_AND_RESULT}} | Not verified |
| Live view, freshness and actual Gateway spans/access logs | {{PRIVATE_VIEW_AND_OBSERVED_IDS}} | Not verified |
| Tempo/log/metrics-store evidence | {{SEPARATE_QUERY_RECEIPTS}} | Not verified |
| Invalid-binding, revocation and reset/retirement drill | {{SCOPED_DRILL_RECEIPTS}} | Not verified |

**What remains:** {{EXACT_GAPS_OWNERS_AND_NEXT_ACTIONS}}

**Run it again:** {{REVIEWED_APPLY_INVOKE_WATCH_AND_RESET_COMMANDS}}

**Operational ownership:** {{OPERATOR_GATEWAY_IDENTITY_CONTENT_REGISTRY_OBSERVABILITY_OWNERS}}

Record approval/token lifetimes and renewal limitations privately without including token values. Note in-memory session limits or Job completion where applicable. Preserve evidence labels for synthetic documentation/tools, historical lab results and actual office execution. Substrate, Entra and untested isolation claims remain outside this session.
