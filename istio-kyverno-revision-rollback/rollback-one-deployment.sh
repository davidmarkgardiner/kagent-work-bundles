#!/usr/bin/env bash
# The incident diagnosis changed. Prevent the earlier namespace rollback.
echo 'SUPERSEDED: this incident concerns a PeerAuthentication label 1-29 -> 1-23.' >&2
echo 'Use patch-peerauthentication-revision.sh. Do not roll back namespaces or workloads for this policy-only correction.' >&2
exit 2
