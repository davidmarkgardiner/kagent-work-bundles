{{- define "flow.image" -}}
{{- if .Values.image.digest -}}
{{ .Values.image.repository }}@{{ .Values.image.digest }}
{{- else -}}
{{ .Values.image.repository }}:{{ .Values.image.tag }}
{{- end -}}
{{- end -}}

{{- define "flow.instruction" -}}
{{- if eq .Values.tools.mode "live" -}}
You inspect actual Kubernetes and GitLab data using only the registered read tools.
Call only the tools requested by the user. Kubernetes scope is namespace {{ .Release.Namespace }}.
When requested, call k8s_get_resources with resource_type deployment, namespace {{ .Release.Namespace }}, and output wide.
GitLab tools are fixed to one approved project. Read current project metadata,
up to five recent issues, and latest pipeline status when requested. Never invent
results or claim that fixture data is live. State tool errors clearly. Do not
mutate Kubernetes, create issues, trigger pipelines, or write GitLab content.
{{- else -}}
You demonstrate agent workflows. Follow the requested DEMO_WORKFLOW by calling the named tools in order.
All tool data is explicitly simulated. Explain fixture results and intentional dependency failures clearly.
Never claim to have inspected or changed the real cluster. Do not retry a simulated failure.
Never invent telemetry, token prices, deployments, or approvals.
{{- end -}}
{{- end -}}
{{- define "flow.toolConnections" -}}
{{- if eq .Values.tools.mode "live" -}}
{{ list (dict "server" "flow-kubernetes-tools" "service" "flow-kubernetes-mcp" "tools" (list "k8s_get_resources" "k8s_get_events")) (dict "server" "flow-gitlab-tools" "service" "flow-gitlab-mcp" "tools" (list "gitlab_get_project" "gitlab_list_issues" "gitlab_get_latest_pipeline")) | toJson }}
{{- else -}}
{{ list (dict "server" "flow-demo-tools" "service" "flow-workflows" "tools" (list "get_inventory_status" "get_recent_alerts" "review_change" "check_dependency" "get_kubernetes_workloads" "query_grafana_alerts" "get_gitlab_issue" "get_gitlab_pipeline" "read_team_a_resource" "attempt_cross_team_resource" "read_team_b_resource")) | toJson }}
{{- end -}}
{{- end -}}

{{- define "flow.executionTargets" -}}
{{- $targets := list -}}
{{- if ne .Values.execution.mode "standalone" -}}
{{- $targets = append $targets (dict "id" "substrate" "mode" "substrate" "label" "With Substrate") -}}
{{- end -}}
{{- if ne .Values.execution.mode "substrate" -}}
{{- $targets = append $targets (dict "id" "standalone" "mode" "standalone" "label" "Without Substrate" "url" (printf "http://flow-standalone.%s.svc.cluster.local:8080/" .Release.Namespace)) -}}
{{- end -}}
{{ $targets | toJson }}
{{- end -}}
