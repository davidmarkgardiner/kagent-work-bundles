import { addTimeline, buildConclusion, createPendingAction } from "./workflow.mjs";

export class IncidentCoordinator {
  constructor({ store, investigators, publisher = null, executor = null }) {
    this.store = store;
    this.investigators = investigators;
    this.publisher = publisher;
    this.executor = executor;
    this.inFlight = new Map();
  }

  start(id) {
    if (this.inFlight.has(id)) return this.inFlight.get(id);
    const task = this.#investigate(id).finally(() => this.inFlight.delete(id));
    this.inFlight.set(id, task);
    return task;
  }

  async #investigate(id) {
    await this.store.update(id, (record) => {
      if (record.state !== "received") return;
      record.state = "investigating";
      addTimeline(record, "investigation.started", "Read-only investigators dispatched");
    });
    let current = await this.store.get(id);
    if (current.state === "investigating") {
      const results = await Promise.all(this.investigators.map(async (investigator) => {
        try { return { name: investigator.name, result: await investigator.investigate(current.incident, id) }; }
        catch (error) { return { name: investigator.name, error }; }
      }));
      await this.store.update(id, (record) => {
        for (const item of results) {
          if (item.result) {
            record.sessions[item.name] = item.result.session;
            record.findings.push(...item.result.findings);
            addTimeline(record, "investigator.completed", `${item.name} returned ${item.result.findings.length} finding(s)`);
          } else if (item.error) {
            record.findings.push({ id: `${item.name}-error`, source: item.name, agent: item.name, status: "degraded", evidence: item.error.message });
            addTimeline(record, "investigator.degraded", `${item.name} failed without blocking the incident`);
          }
        }
        record.conclusion = buildConclusion(record.incident);
        record.state = "publishing_outputs";
        addTimeline(record, "outputs.started", "Publishing the durable GitLab incident output");
      });
      current = await this.store.get(id);
    }
    if (current.state !== "publishing_outputs") return current;
    let outputError = null;
    if (this.publisher) {
      try {
        const latest = await this.store.get(id);
        const output = await this.publisher.publish(latest, async (gitlab) => this.store.update(id, (record) => { record.outputs ??= {}; record.outputs.gitlab = gitlab; addTimeline(record, "gitlab.checkpoint", "GitLab output checkpoint saved"); }));
        if (output) await this.store.update(id, (record) => { record.outputs.gitlab = output; addTimeline(record, "gitlab.published", output.merge_request ? `Issue #${output.issue.iid} and draft MR !${output.merge_request.iid} published` : `Issue #${output.issue.iid} published`); });
      } catch (error) { outputError = error; }
    }
    return this.store.update(id, (record) => {
      if (outputError) {
        record.findings.push({ id: "gitlab-output-error", source: "gitlab-mcp", agent: "GitLab output", status: "degraded", evidence: outputError.message });
        addTimeline(record, "gitlab.degraded", "GitLab output failed; no remote action approval was created");
      }
      if (record.incident.approval_flow === "merge_request" && !record.outputs.gitlab?.merge_request) {
        record.state = "output_failed";
        return;
      }
      record.pending_action = createPendingAction(record);
      record.state = "waiting_approval";
      addTimeline(record, "approval.required", `${record.pending_action.action_type} proposal is pending a human decision; no action was executed`);
    });
  }

  async decide(id, { decision, action_id: actionId }, actor) {
    if (!["approved", "rejected"].includes(decision)) throw Object.assign(new Error("decision must be approved or rejected"), { statusCode: 400 });
    const current = await this.store.get(id);
    if (current?.state === "waiting_approval" && current.pending_action && Date.parse(current.pending_action.expires_at) <= Date.now()) {
      await this.store.update(id, (record) => {
        record.state = "approval_expired";
        record.pending_action = null;
        addTimeline(record, "approval.expired", "The 72-hour approval window expired; no action was executed");
      });
      throw Object.assign(new Error("approval action has expired"), { statusCode: 409 });
    }
    const decided = await this.store.update(id, (record) => {
      if (record.state !== "waiting_approval" || !record.pending_action) throw Object.assign(new Error("incident has no pending approval"), { statusCode: 409 });
      if (record.pending_action.action_id !== actionId) throw Object.assign(new Error("approval action is stale or does not belong to this incident"), { statusCode: 409 });
      if (Date.parse(record.pending_action.expires_at) <= Date.now()) throw Object.assign(new Error("approval action has expired"), { statusCode: 409 });
      record.decision = { decision, actor, decided_at: new Date().toISOString(), action_id: actionId, action_type: record.pending_action.action_type, proposal_version: record.pending_action.proposal_version };
      record.approved_action = decision === "approved" ? structuredClone(record.pending_action) : null;
      record.pending_action = null;
      record.state = "decision_recorded";
      record.execution = { executed: false, executor: null, receipt: null };
      addTimeline(record, "approval.recorded", `${decision} by ${actor}; executed=false`);
    });
    if (this.publisher) {
      try { await this.publisher.recordDecision(decided); }
      catch (error) { await this.store.update(id, (record) => addTimeline(record, "gitlab.decision_sync_failed", error.message)); }
    }
    return this.store.get(id);
  }

  async execute(id, { action_id: actionId }) {
    if (!this.executor) throw Object.assign(new Error("approved action executor is not configured"), { statusCode: 503 });
    const current = await this.store.get(id);
    if (current?.state === "waiting_approval" && current.pending_action && Date.parse(current.pending_action.expires_at) <= Date.now()) {
      await this.store.update(id, (record) => {
        record.state = "approval_expired";
        record.pending_action = null;
        addTimeline(record, "approval.expired", "The 72-hour approval window expired; no action was executed");
      });
      throw Object.assign(new Error("approval action has expired"), { statusCode: 409 });
    }
    const claimed = await this.store.update(id, (record) => {
      if (record.execution?.executed && record.execution.action_id === actionId) return;
      if (record.state !== "decision_recorded" || record.decision?.decision !== "approved" || !record.approved_action) throw Object.assign(new Error("incident does not have an approved action"), { statusCode: 409 });
      if (record.approved_action.action_id !== actionId) throw Object.assign(new Error("execution action is stale or does not belong to this incident"), { statusCode: 409 });
      record.state = "executing";
      addTimeline(record, "execution.started", `Bounded executor claimed ${record.approved_action.action_type} action ${actionId}`);
    });
    if (claimed.execution?.executed) return claimed;
    try {
      const receipt = await this.executor.execute(claimed);
      const executed = await this.store.update(id, (record) => {
        if (record.approved_action.action_type === "merge_request" && receipt.agent_result?.state === "merged") {
          Object.assign(record.outputs.gitlab.merge_request, {
            state: "merged",
            draft: false,
            merge_performed: true,
            title: record.outputs.gitlab.merge_request.title.replace(/^(Draft:|WIP:)\s*/i, ""),
            merge_commit_sha: receipt.agent_result.merge_commit_sha
          });
        }
        record.state = "executed";
        record.execution = { executed: true, action_id: actionId, executor: this.executor.name, completed_at: new Date().toISOString(), receipt };
        addTimeline(record, "execution.completed", `${record.approved_action.action_type} completed through ${this.executor.name}`);
      });
      if (this.publisher) {
        try { await this.publisher.recordExecution(executed); }
        catch (error) { await this.store.update(id, (record) => addTimeline(record, "gitlab.execution_sync_failed", error.message)); }
      }
      return this.store.get(id);
    } catch (error) {
      await this.store.update(id, (record) => {
        record.state = "execution_failed";
        record.execution = { executed: false, action_id: actionId, executor: this.executor.name, failed_at: new Date().toISOString(), error: error.message, receipt: null };
        addTimeline(record, "execution.failed", error.message);
      });
      throw error;
    }
  }

  async verify(id) {
    const current = await this.store.get(id);
    if (current?.state !== "executed" || !current.execution?.executed) throw Object.assign(new Error("incident has no completed execution to verify"), { statusCode: 409 });
    const results = await Promise.all(this.investigators.map(async (investigator) => {
      try { return { name: investigator.name, result: await investigator.investigate(current.incident, id) }; }
      catch (error) { return { name: investigator.name, error }; }
    }));
    const successful = results.filter((item) => item.result);
    const verified = await this.store.update(id, (record) => {
      record.post_verification = {
        verified: successful.length > 0,
        checked_at: new Date().toISOString(),
        findings: results.flatMap((item) => item.result?.findings ?? [{ id: `${item.name}-verification-error`, source: item.name, agent: item.name, status: "degraded", evidence: item.error.message }])
      };
      record.state = successful.length > 0 ? "resolved" : "verification_failed";
      addTimeline(record, successful.length > 0 ? "verification.completed" : "verification.failed", successful.length > 0 ? "Read-only post-change verification completed" : "No read-only verifier completed successfully");
    });
    if (successful.length > 0 && this.publisher?.recordVerification) {
      try { await this.publisher.recordVerification(verified); }
      catch (error) { await this.store.update(id, (record) => addTimeline(record, "gitlab.verification_sync_failed", error.message)); }
    }
    return this.store.get(id);
  }

  async resolve(id) {
    return this.store.update(id, (record) => {
      if (!["decision_recorded", "executed"].includes(record.state)) throw Object.assign(new Error("record a decision before resolving the incident"), { statusCode: 409 });
      record.state = "resolved";
      record.resolution = { at: new Date().toISOString(), summary: record.execution?.executed ? "Resolved after approved execution." : "Resolved without execution." };
      addTimeline(record, "incident.resolved", record.resolution.summary);
    });
  }
}
