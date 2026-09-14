apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: incident-lifecycle
  namespace: ${ARGO_WORKFLOWS_NAMESPACE}
spec:
  entrypoint: lifecycle
  serviceAccountName: incident-workflow
  podGC: {strategy: OnWorkflowCompletion}
  ttlStrategy: {secondsAfterCompletion: 604800}
  arguments:
    parameters:
      - {name: incident, value: "{}"}
  templates:
    - name: lifecycle
      dag:
        tasks:
          - name: intake
            template: intake
          - name: await-investigation
            dependencies: [intake]
            template: await-investigation
            arguments:
              parameters:
                - {name: incident-id, value: "{{tasks.intake.outputs.parameters.incident-id}}"}
          - name: notify
            dependencies: [await-investigation]
            template: notify
            arguments:
              parameters:
                - {name: incident-id, value: "{{tasks.intake.outputs.parameters.incident-id}}"}
          - name: human-approval
            dependencies: [notify]
            template: human-approval
          - name: execute-approved-action
            dependencies: [human-approval]
            template: execute
            arguments:
              parameters:
                - {name: incident-id, value: "{{tasks.intake.outputs.parameters.incident-id}}"}
                - {name: action-id, value: "{{tasks.await-investigation.outputs.parameters.action-id}}"}
          - name: verify-live-state
            dependencies: [execute-approved-action]
            template: verify
            arguments:
              parameters:
                - {name: incident-id, value: "{{tasks.intake.outputs.parameters.incident-id}}"}
    - name: intake
      outputs:
        parameters:
          - {name: incident-id, valueFrom: {path: /tmp/incident-id}}
      script:
        image: badouralix/curl-jq:alpine
        command: [sh]
        env:
          - name: TOKEN
            valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: intake-token}}
        source: |
          set -eu
          cat > /tmp/incident.json <<'INCIDENT'
          {{workflow.parameters.incident}}
          INCIDENT
          jq --arg workflow "{{workflow.name}}" --arg namespace "{{workflow.namespace}}" '.workflow_name=$workflow | .workflow_namespace=$namespace' /tmp/incident.json >/tmp/request.json
          curl --fail --silent --show-error --retry 3 -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' --data @/tmp/request.json http://incident-coordinator.${INCIDENT_NAMESPACE}.svc.cluster.local:4173/api/incidents >/tmp/response.json
          jq -er .id /tmp/response.json >/tmp/incident-id
    - name: await-investigation
      inputs:
        parameters:
          - name: incident-id
      outputs:
        parameters:
          - {name: action-id, valueFrom: {path: /tmp/action-id}}
      script:
        image: badouralix/curl-jq:alpine
        command: [sh]
        env:
          - name: TOKEN
            valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: read-token}}
        source: |
          set -eu
          n=0
          while [ "$n" -lt 90 ]; do
            curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" "http://incident-coordinator.${INCIDENT_NAMESPACE}.svc.cluster.local:4173/api/incidents/{{inputs.parameters.incident-id}}" >/tmp/record.json
            state=$(jq -r .state /tmp/record.json)
            case "$state" in
              waiting_approval)
                jq -er .pending_action.action_id /tmp/record.json >/tmp/action-id
                exit 0
                ;;
              output_failed|execution_failed)
                jq -r . /tmp/record.json >&2
                exit 1
                ;;
            esac
            n=$((n + 1))
            sleep 5
          done
          echo "investigation did not reach approval within 450 seconds" >&2
          exit 1
    - name: notify
      inputs:
        parameters:
          - name: incident-id
      script:
        image: curlimages/curl:8.9.1
        command: [sh]
        env:
          - name: TOKEN
            valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: intake-token}}
        source: |
          curl --fail --silent --show-error --retry 3 -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' "http://incident-coordinator.${INCIDENT_NAMESPACE}.svc.cluster.local:4173/api/incidents/{{inputs.parameters.incident-id}}/notified"
    - name: human-approval
      suspend:
        duration: 72h
    - name: execute
      inputs:
        parameters:
          - name: incident-id
          - name: action-id
      script:
        image: curlimages/curl:8.9.1
        command: [sh]
        env:
          - name: TOKEN
            valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: executor-token}}
        source: |
          set -eu
          curl --fail --silent --show-error -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"action_id":"{{inputs.parameters.action-id}}"}' "http://incident-coordinator.${INCIDENT_NAMESPACE}.svc.cluster.local:4173/api/incidents/{{inputs.parameters.incident-id}}/execute"
    - name: verify
      inputs:
        parameters:
          - name: incident-id
      script:
        image: curlimages/curl:8.9.1
        command: [sh]
        env:
          - name: TOKEN
            valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: executor-token}}
        source: |
          curl --fail --silent --show-error -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' "http://incident-coordinator.${INCIDENT_NAMESPACE}.svc.cluster.local:4173/api/incidents/{{inputs.parameters.incident-id}}/verify"
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: incident-workflow
  namespace: ${ARGO_WORKFLOWS_NAMESPACE}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: incident-workflow-executor
  namespace: ${ARGO_WORKFLOWS_NAMESPACE}
rules:
  - apiGroups: [argoproj.io]
    resources: [workflowtaskresults]
    verbs: [create, patch]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: incident-workflow-executor
  namespace: ${ARGO_WORKFLOWS_NAMESPACE}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: incident-workflow-executor
subjects:
  - kind: ServiceAccount
    name: incident-workflow
    namespace: ${ARGO_WORKFLOWS_NAMESPACE}
