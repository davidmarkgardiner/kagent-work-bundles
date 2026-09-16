# Decision record: pause the high-volume triage rollout

Status: draft for internal review. This document does not confirm that the
system has been disabled, and the team message below has not been sent.

Date: 2026-09-16

## Decision

Disable and suspend the existing event-by-event triage rollout. Do not enable
it again until the teams agree a staffed transition plan with named, qualified
engineers, clear ownership, and tested rollback controls.

Continue the cluster-health assessment work as the lower-impact alternative.
That design collects evidence throughout the day but emits at most one bounded
health record for each cluster and UTC date. Only an unhealthy record can start
a read-only agent investigation. A separate writer can create or update one
managed GitLab issue after explicit approval.

The cluster-health bundle is ready for workplace testing. It is not deployed
or approved for production use.

## What happened

The rollout produced approximately 20,000 GitLab tickets. The system was
enabled on a Friday evening and remained active through the weekend and a
Monday holiday. The transition support that had been agreed in advance did not
materialize during this period.

When the volume became visible, the available response was too slow to bring
the rollout under control. The application team prepared an urgent merge
request to disable the three namespaces responsible for most of the noise.

The incident exposed two separate problems:

- The triage path could turn a large number of related symptoms into separate
  tickets without an effective cluster-level health gate.
- The operating model depended on SRE support that was not available when the
  rollout needed active monitoring, diagnosis, and rollback decisions.

The first problem is technical. The second problem prevents a safe transition
even if the ticket logic improves.

## Why the rollout is paused

The agreed support commitment was not met. We do not currently know who will
monitor the rollout, who will respond within the change window, or who has the
authority and experience to stop it when ticket volume rises unexpectedly.

This leaves us without enough operational confidence in the cross-team support
model. Continuing would expose users and support teams to another uncontrolled
ticket burst.

This decision is about observed coverage, ownership, and response. It does not
assign blame to an individual. The project can restart when the support model
is specific, staffed, and tested.

## Conditions for restarting the original project

Do not restart the high-volume triage path until all of these conditions are
met:

1. Name an accountable SRE owner, a primary engineer, and a backup engineer.
2. Schedule a staffed change window. Each named engineer must acknowledge the
   window before enablement.
3. Define response and escalation times for ticket bursts, Kafka failures,
   agent failures, and incorrect routing.
4. Start with one canary namespace and a fixed maximum ticket rate.
5. Add an automatic circuit breaker that stops publication when the rate or
   backlog exceeds the approved limit.
6. Test the disablement and rollback procedure before the rollout.
7. Confirm the worker cluster is healthy before the first signal is admitted.
8. Record a named go or no-go decision at the start and end of the change
   window.
9. Keep the change attended until the agreed stability period has completed.

A verbal assurance that support will be available is not enough. The restart
plan must name the people, times, controls, and decision owners.

## Lower-impact path

The replacement pilot uses the
[cluster-health workplace bundle](workplace-bundle/README.md):

- Fox and B1 collect current evidence without creating per-finding tickets.
- B1 calculates five domain states and a display score every five minutes.
- A deterministic gate handles critical, sustained degraded, and recovery
  states.
- The controller emits one bounded Kafka record after the configured daily
  time.
- Healthy records do not start a Workflow, agent, or GitLab call.
- Unhealthy records start one replay-safe, read-only investigation.
- The agent groups related symptoms under the smallest credible root causes.
- The GitLab writer is disabled by default. When approved, it creates or
  updates one labelled cluster summary issue.
- The agent cannot change Kubernetes resources or access the GitLab token.

This path reduces operational impact, but it still needs the workplace gates
in the [test plan](workplace-bundle/TEST-PLAN.md). Internal image builds, Kafka
delivery, AKS-MCP access, effective permissions, GitLab behavior, and the soak
period remain unproven in the workplace environment.

The [visual explainer](workplace-bundle/CLUSTER-HEALTH-VISUAL.html) shows the
complete flow.

## Team message draft

Confirm that the existing triage path has been disabled before sending this
message.

> Team,
>
> We have decided to disable and pause the current event-by-event triage
> rollout.
>
> The latest activation generated approximately 20,000 GitLab tickets after
> it was enabled before the weekend and remained active through the holiday
> period. The SRE transition support that had been agreed in advance was not
> available when the rollout needed active monitoring and control. The response
> after the volume became visible was also too slow to make continued operation
> safe. We had to prepare an urgent change to disable the three namespaces that
> produced most of the noise.
>
> The agreed support commitment was not met. As a result, we do not currently
> have enough confidence in the cross-team operating model to continue this
> rollout. This is an operational decision based on the coverage, ownership,
> and response that were available. It is not a judgment about any one person.
>
> The original project will remain disabled until we have a named SRE owner,
> qualified primary and backup engineers, a staffed change window, tested
> rollback controls, a canary scope, and an agreed response path. We will not
> rely on an informal assurance of support for another high-impact rollout.
>
> In the meantime, we are moving to a lower-impact cluster-health approach. It
> collects current cluster evidence but emits at most one health summary per
> day. Only an unhealthy result starts a read-only investigation, and the
> proposed GitLab integration maintains one cluster-level SRE issue instead of
> creating one issue for each event, log error, or pod symptom. It performs no
> automatic remediation.
>
> We will test that alternative through the normal image, Kafka, permission,
> agent, GitLab, rollback, and soak gates before any production enablement.
> Please do not re-enable any part of the original triage path without an agreed
> restart review and named support coverage.

## Suggested record owners

Before publishing this decision internally, add the workplace references for:

- the disablement merge request and its deployment status;
- the incident or problem record;
- the original rollout approval and support commitment;
- the confirmed ticket count and affected time window;
- the owner who approves any future restart.

Keep internal names, project URLs, ticket identifiers, and incident evidence
out of this public repository.
