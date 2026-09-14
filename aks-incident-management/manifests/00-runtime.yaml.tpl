apiVersion: v1
kind: Namespace
metadata:
  name: ${INCIDENT_NAMESPACE}
  labels:
    app.kubernetes.io/part-of: aks-incident-management
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: incident-coordinator
  namespace: ${INCIDENT_NAMESPACE}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: incident-coordinator-kagent-read
  namespace: kagent
rules:
  - apiGroups: [kagent.dev]
    resources: [agents]
    resourceNames: [${INVESTIGATOR_AGENT_NAME}]
    verbs: [get]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: incident-coordinator-kagent-read
  namespace: kagent
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: incident-coordinator-kagent-read
subjects:
  - kind: ServiceAccount
    name: incident-coordinator
    namespace: ${INCIDENT_NAMESPACE}
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: incident-postgres
  namespace: ${INCIDENT_NAMESPACE}
spec:
  serviceName: incident-postgres
  replicas: 1
  selector:
    matchLabels: {app: incident-postgres}
  template:
    metadata:
      labels: {app: incident-postgres}
    spec:
      containers:
        - name: postgres
          image: postgres:17-alpine
          env:
            - {name: POSTGRES_DB, value: incidents}
            - {name: POSTGRES_USER, valueFrom: {secretKeyRef: {name: incident-postgres-auth, key: username}}}
            - {name: POSTGRES_PASSWORD, valueFrom: {secretKeyRef: {name: incident-postgres-auth, key: password}}}
          ports: [{name: postgres, containerPort: 5432}]
          readinessProbe:
            exec: {command: [sh, -c, 'pg_isready -U "$POSTGRES_USER" -d incidents']}
          volumeMounts: [{name: data, mountPath: /var/lib/postgresql/data}]
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 500m, memory: 512Mi}
  volumeClaimTemplates:
    - metadata: {name: data}
      spec:
        accessModes: [ReadWriteOnce]
        resources: {requests: {storage: 5Gi}}
---
apiVersion: v1
kind: Service
metadata:
  name: incident-postgres
  namespace: ${INCIDENT_NAMESPACE}
spec:
  selector: {app: incident-postgres}
  ports: [{name: postgres, port: 5432, targetPort: postgres}]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: incident-coordinator
  namespace: ${INCIDENT_NAMESPACE}
spec:
  replicas: 1
  strategy: {type: Recreate}
  selector:
    matchLabels: {app: incident-coordinator}
  template:
    metadata:
      labels: {app: incident-coordinator}
    spec:
      serviceAccountName: incident-coordinator
      securityContext: {runAsNonRoot: true, runAsUser: 1000, runAsGroup: 1000, seccompProfile: {type: RuntimeDefault}}
      containers:
        - name: coordinator
          image: ${COORDINATOR_IMAGE}
          imagePullPolicy: IfNotPresent
          ports: [{name: http, containerPort: 4173}]
          env:
            - {name: INCIDENT_STORE_BACKEND, value: postgres}
            - {name: KAFKA_TOPIC, value: "${KAFKA_TOPIC}"}
            - {name: KAGENT_A2A_URL, value: "${KAGENT_A2A_URL}"}
            - {name: KAGENT_AGENT_NAME, value: "${INVESTIGATOR_AGENT_NAME}"}
            - {name: KAGENT_MODEL_LABEL, value: "${MODEL_LABEL}"}
            - {name: KAGENT_EXECUTOR_A2A_URL, value: "${KAGENT_EXECUTOR_A2A_URL}"}
            - {name: KAGENT_EXECUTOR_AGENT_NAME, value: "${EXECUTOR_AGENT_NAME}"}
            - {name: GITLAB_MCP_URL, value: "${GITLAB_MCP_URL}"}
            - {name: GITOPS_FILE_PATH, value: "${GITOPS_FILE_PATH}"}
            - {name: TEAMS_APPROVAL_URL, value: "${TEAMS_APPROVAL_URL}"}
            - {name: SERVICENOW_RELAY_URL, value: "${SERVICENOW_RELAY_URL}"}
            - {name: APPROVAL_CALLBACK_BASE_URL, value: "${APPROVAL_CALLBACK_BASE_URL}"}
            - {name: ARGO_APPROVAL_CALLBACK_URL, value: "${ARGO_APPROVAL_CALLBACK_URL}"}
            - {name: ARGO_UI_BASE_URL, value: "${ARGO_UI_BASE_URL}"}
            - {name: INVESTIGATION_NAMESPACE_ALLOWLIST, value: "${REMEDIATION_NAMESPACE}"}
            - name: DATABASE_URL
              valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: database-url}}
            - name: INCIDENT_INGEST_TOKEN
              valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: intake-token}}
            - name: INCIDENT_READ_TOKEN
              valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: read-token}}
            - name: DEMO_AUTH_TOKEN
              valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: approval-token}}
            - name: INCIDENT_EXECUTOR_TOKEN
              valueFrom: {secretKeyRef: {name: incident-runtime-auth, key: executor-token}}
            - name: TEAMS_RELAY_TOKEN
              valueFrom: {secretKeyRef: {name: incident-integration-auth, key: teams-token, optional: true}}
            - name: SERVICENOW_RELAY_TOKEN
              valueFrom: {secretKeyRef: {name: incident-integration-auth, key: servicenow-token, optional: true}}
          readinessProbe: {httpGet: {path: /healthz, port: http}, initialDelaySeconds: 5, periodSeconds: 10}
          livenessProbe: {httpGet: {path: /livez, port: http}, initialDelaySeconds: 10, periodSeconds: 20}
          securityContext: {allowPrivilegeEscalation: false, capabilities: {drop: [ALL]}, readOnlyRootFilesystem: true}
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: "1", memory: 512Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: incident-coordinator
  namespace: ${INCIDENT_NAMESPACE}
spec:
  selector: {app: incident-coordinator}
  ports: [{name: http, port: 4173, targetPort: http}]
