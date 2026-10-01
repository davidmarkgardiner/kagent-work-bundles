# Cert Manager HTTP01 self-check: lab retrieval fixture

Document ID: cert-manager-http01-lab
Revision: 2026-10-01
Reviewed on: 2026-10-01
Review after: 2026-10-31
Status: synthetic lab guidance; workplace owner approval required
Component: cert-manager
Applicability: HTTP01 ACME challenge troubleshooting; installed version must be checked
Namespace scope: generic component guidance; no namespace-specific incident history
Source: https://cert-manager.io/docs/troubleshooting/acme/

This fixture illustrates document retrieval, not a previous workplace incident.
For a reported pending HTTP01 challenge or self-check failure, inspect the
Issuer readiness, CertificateRequest, Order and Challenge status/reason before
forming a diagnosis. A challenge self-check can involve DNS or HTTP routing;
an ingress class mismatch is one possible hypothesis, not an established cause.
Request a bounded read of the affected Challenge and related solver Ingress and
Service in the certificate namespace. Compare configured solver routing with
the intended ingress controller. Topology alone cannot establish HTTP response,
DNS resolution or current certificate issuance status. Do not restart the
controller or alter an Issuer solely because this document was retrieved.
Changes require an approved workflow or GitOps review with verification.
