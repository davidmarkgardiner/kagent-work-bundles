# Run the Dice daily cluster-health report

This schedule runs the existing `cluster-certification` WorkflowTemplate at 07:00 Europe/London. It starts suspended. The WorkflowTemplate defaults to `log-only`, so a failed check can call the read-only cluster-health agent but cannot create a ticket or change the cluster.

## Install and prove the first run

Apply the existing health assets, then add the schedule:

```sh
kubectl --context red apply -f agents/cluster-health-sentinel/01-rbac.yaml
kubectl --context red apply -f agents/cluster-health-sentinel/02-collector-configmap.yaml
kubectl --context red apply -f agents/cluster-health-sentinel/06-baselines-configmap.yaml
kubectl --context red apply -f agents/cluster-health-sentinel/03-certification-workflow.yaml
kubectl --context red apply -f work-agent-bundles/dice-programme/daily-health/cronworkflow.yaml
```

Submit one manual run before you enable the schedule:

```sh
argo submit --kube-context red -n argo-events \
  --from workflowtemplate/cluster-certification \
  -p cluster-name=red \
  --watch
```

Read the `aggregate` output and any `agent-triage` result. Confirm that `cluster-certification-config` still contains `report-mode: log-only`.

The `cluster-health-orchestrator` Deployment must have a Ready replica before the Workflow calls it. The lab keeps that Deployment at zero replicas while the schedule is suspended. Do not enable the schedule until the work environment either keeps one replica Ready or has a tested activation mechanism that waits for readiness before the A2A call.

## Enable the schedule

Enable it only after the team accepts the first report and baseline thresholds:

```sh
kubectl --context red -n argo-events patch cronworkflow dice-daily-cluster-health \
  --type merge -p '{"spec":{"suspend":false}}'
```

To stop future runs, set `spec.suspend` back to `true`. Existing Workflow records remain available for review.

## Connect failed reports to incident triage

Keep healthy reports out of the incident queue. For a failed check or a changed baseline, normalize the report into the incident contract and send it through the existing Kafka and Argo intake. Include the cluster, failed checks, report timestamp, report hash, and source Workflow name in the fingerprint.

The incident coordinator then performs a fresh read-only investigation. It can create a recommendation and ticket. Do not enable a writer until the coordinator has produced a specific target-bound action that the existing approval workflow can bind and recheck.
