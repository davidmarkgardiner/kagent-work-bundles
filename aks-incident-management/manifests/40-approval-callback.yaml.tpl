apiVersion: argoproj.io/v1alpha1
kind: EventSource
metadata:
  name: incident-approval-callback
  namespace: ${ARGO_EVENTS_NAMESPACE}
spec:
  service:
    ports: [{port: 12000, targetPort: 12000}]
  webhook:
    approval:
      port: "12000"
      endpoint: /approval-callback
      method: POST
---
apiVersion: argoproj.io/v1alpha1
kind: Sensor
metadata:
  name: incident-approval-approved
  namespace: ${ARGO_EVENTS_NAMESPACE}
spec:
  template: {serviceAccountName: argo-events-sa}
  dependencies:
    - name: approved
      eventSourceName: incident-approval-callback
      eventName: approval
      filters:
        data:
          - {path: body.decision, type: string, value: [approved]}
          - {path: body.workflow_namespace, type: string, value: ["${ARGO_WORKFLOWS_NAMESPACE}"]}
          - {path: body.approval_id, type: string, value: ["[A-Za-z0-9._:-]{8,}"]}
  triggers:
    - template:
        name: resume
        argoWorkflow:
          operation: resume
          source:
            resource:
              apiVersion: argoproj.io/v1alpha1
              kind: Workflow
              metadata: {name: "", namespace: ${ARGO_WORKFLOWS_NAMESPACE}}
          parameters:
            - {src: {dependencyName: approved, dataKey: body.workflow_name}, dest: metadata.name}
      conditions: approved
---
apiVersion: argoproj.io/v1alpha1
kind: Sensor
metadata:
  name: incident-approval-rejected
  namespace: ${ARGO_EVENTS_NAMESPACE}
spec:
  template: {serviceAccountName: argo-events-sa}
  dependencies:
    - name: rejected
      eventSourceName: incident-approval-callback
      eventName: approval
      filters:
        data:
          - {path: body.decision, type: string, value: [rejected, expired]}
          - {path: body.workflow_namespace, type: string, value: ["${ARGO_WORKFLOWS_NAMESPACE}"]}
  triggers:
    - template:
        name: stop
        argoWorkflow:
          operation: stop
          source:
            resource:
              apiVersion: argoproj.io/v1alpha1
              kind: Workflow
              metadata: {name: "", namespace: ${ARGO_WORKFLOWS_NAMESPACE}}
          parameters:
            - {src: {dependencyName: rejected, dataKey: body.workflow_name}, dest: metadata.name}
      conditions: rejected
