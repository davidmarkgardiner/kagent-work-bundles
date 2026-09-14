apiVersion: v1
kind: ServiceAccount
metadata:
  name: incident-executor
  namespace: ${INCIDENT_NAMESPACE}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: incident-executor-label
  namespace: ${REMEDIATION_NAMESPACE}
rules:
  - apiGroups: [apps]
    resources: [deployments]
    resourceNames: [${REMEDIATION_DEPLOYMENT}]
    verbs: [get, patch]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: incident-executor-label
  namespace: ${REMEDIATION_NAMESPACE}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: incident-executor-label
subjects:
  - kind: ServiceAccount
    name: incident-executor
    namespace: ${INCIDENT_NAMESPACE}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: incident-executor-mcp
  namespace: ${INCIDENT_NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels: {app: incident-executor-mcp}
  template:
    metadata:
      labels: {app: incident-executor-mcp}
    spec:
      serviceAccountName: incident-executor
      securityContext: {runAsNonRoot: true, runAsUser: 1000, runAsGroup: 1000, seccompProfile: {type: RuntimeDefault}}
      containers:
        - name: executor
          image: ${COORDINATOR_IMAGE}
          command: [node, src/executor-mcp.mjs]
          ports: [{name: mcp, containerPort: 8080}]
          env:
            - {name: PORT, value: "8080"}
            - {name: REMEDIATION_NAMESPACE, value: "${REMEDIATION_NAMESPACE}"}
            - {name: REMEDIATION_DEPLOYMENT, value: "${REMEDIATION_DEPLOYMENT}"}
            - {name: REMEDIATION_LABEL_KEY, value: "${REMEDIATION_LABEL_KEY}"}
            - {name: REMEDIATION_LABEL_VALUE, value: "${REMEDIATION_LABEL_VALUE}"}
            - {name: GITLAB_PROJECT_PATH, value: "${GITLAB_PROJECT_PATH}"}
            - {name: GITLAB_TARGET_BRANCH, value: "${GITLAB_TARGET_BRANCH}"}
            - name: GITLAB_TOKEN
              valueFrom: {secretKeyRef: {name: incident-gitlab-executor, key: token, optional: true}}
          securityContext: {allowPrivilegeEscalation: false, capabilities: {drop: [ALL]}, readOnlyRootFilesystem: true}
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 500m, memory: 256Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: incident-executor-mcp
  namespace: ${INCIDENT_NAMESPACE}
spec:
  selector: {app: incident-executor-mcp}
  ports: [{name: mcp, port: 8080, targetPort: mcp}]
---
apiVersion: kagent.dev/v1alpha2
kind: RemoteMCPServer
metadata:
  name: incident-executor-mcp
  namespace: kagent
spec:
  description: Approval-bound Kubernetes and GitLab executor. Every target is configured and checked twice.
  protocol: STREAMABLE_HTTP
  url: http://incident-executor-mcp.${INCIDENT_NAMESPACE}.svc.cluster.local:8080
  timeout: 120s
  sseReadTimeout: 5m0s
