apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: incident-events-workflows
  namespace: ${ARGO_WORKFLOWS_NAMESPACE}
rules:
  - apiGroups: [argoproj.io]
    resources: [workflows]
    verbs: [create, get, list, watch, patch, update]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: incident-events-workflows
  namespace: ${ARGO_WORKFLOWS_NAMESPACE}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: incident-events-workflows
subjects:
  - kind: ServiceAccount
    name: argo-events-sa
    namespace: ${ARGO_EVENTS_NAMESPACE}
---
apiVersion: argoproj.io/v1alpha1
kind: EventSource
metadata:
  name: incident-redpanda-local
  namespace: ${ARGO_EVENTS_NAMESPACE}
  labels:
    app.kubernetes.io/part-of: aks-incident-management
    incident.management/environment: local-lab
spec:
  eventBusName: default
  template:
    serviceAccountName: argo-events-sa
  kafka:
    incidents:
      url: "${KAFKA_BOOTSTRAP_SERVERS}"
      topic: "${KAFKA_TOPIC}"
      jsonBody: true
      partition: "0"
---
apiVersion: argoproj.io/v1alpha1
kind: Sensor
metadata:
  name: incident-redpanda-local
  namespace: ${ARGO_EVENTS_NAMESPACE}
  labels:
    app.kubernetes.io/part-of: aks-incident-management
    incident.management/environment: local-lab
spec:
  eventBusName: default
  template:
    serviceAccountName: argo-events-sa
  dependencies:
    - name: incident
      eventSourceName: incident-redpanda-local
      eventName: incidents
      filters:
        data:
          - {path: body.fingerprint, type: string, value: ["^.{1,200}$"]}
  triggers:
    - template:
        name: start-incident
        k8s:
          operation: create
          source:
            resource:
              apiVersion: argoproj.io/v1alpha1
              kind: Workflow
              metadata:
                generateName: incident-local-
                namespace: ${ARGO_WORKFLOWS_NAMESPACE}
                labels:
                  app.kubernetes.io/part-of: aks-incident-management
                  incident.management/environment: local-lab
              spec:
                workflowTemplateRef: {name: incident-lifecycle}
                arguments:
                  parameters:
                    - {name: incident, value: "{}"}
          parameters:
            - src: {dependencyName: incident, dataKey: body}
              dest: spec.arguments.parameters.0.value
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${REMEDIATION_DEPLOYMENT}
  namespace: ${REMEDIATION_NAMESPACE}
  labels:
    app.kubernetes.io/part-of: aks-incident-management
    incident.management/environment: local-lab
spec:
  replicas: 1
  selector:
    matchLabels: {incident.management/target: label-remediation}
  template:
    metadata:
      labels: {incident.management/target: label-remediation}
    spec:
      containers:
        - name: pause
          image: registry.k8s.io/pause:3.10
          resources:
            requests: {cpu: 5m, memory: 8Mi}
            limits: {cpu: 20m, memory: 16Mi}
