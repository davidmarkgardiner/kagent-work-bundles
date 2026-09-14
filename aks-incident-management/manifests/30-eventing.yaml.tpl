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
  name: incident-kafka
  namespace: ${ARGO_EVENTS_NAMESPACE}
spec:
  template:
    serviceAccountName: argo-events-sa
  kafka:
    incidents:
      url: "${KAFKA_BOOTSTRAP_SERVERS}"
      topic: "${KAFKA_TOPIC}"
      consumerGroup: {groupName: aks-incident-management-v1}
      jsonBody: true
      version: "2.5.0"
      tls:
        caCertSecret: {name: ${KAFKA_CREDENTIALS_SECRET}, key: ca.pem}
      sasl:
        mechanism: PLAIN
        userSecret: {name: ${KAFKA_CREDENTIALS_SECRET}, key: key}
        passwordSecret: {name: ${KAFKA_CREDENTIALS_SECRET}, key: secret}
---
apiVersion: argoproj.io/v1alpha1
kind: Sensor
metadata:
  name: incident-kafka
  namespace: ${ARGO_EVENTS_NAMESPACE}
spec:
  eventBusName: default
  template:
    serviceAccountName: argo-events-sa
  dependencies:
    - name: incident
      eventSourceName: incident-kafka
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
                generateName: incident-
                namespace: ${ARGO_WORKFLOWS_NAMESPACE}
                labels:
                  app.kubernetes.io/part-of: aks-incident-management
              spec:
                workflowTemplateRef: {name: incident-lifecycle}
                arguments:
                  parameters:
                    - {name: incident, value: "{}"}
          parameters:
            - src: {dependencyName: incident, dataKey: body}
              dest: spec.arguments.parameters.0.value
