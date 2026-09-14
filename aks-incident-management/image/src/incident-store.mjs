import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { createIncidentRecord, incidentIdFor } from "./workflow.mjs";

export class IncidentStore {
  constructor(path) {
    this.path = path;
    this.data = { schema_version: 1, incidents: {} };
    this.writeChain = Promise.resolve();
  }

  async load() {
    try {
      this.data = JSON.parse(await readFile(this.path, "utf8"));
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
      await this.#write(this.data);
    }
    return this;
  }

  list() {
    return Object.values(this.data.incidents).sort((a, b) => b.last_seen.localeCompare(a.last_seen));
  }

  get(id) {
    return this.data.incidents[id] ?? null;
  }

  async upsert(incident) {
    return this.#transaction((next) => {
      const id = incidentIdFor(incident.fingerprint);
      const existing = next.incidents[id];
      if (existing) {
        existing.delivery_count += 1;
        existing.last_seen = new Date().toISOString();
        existing.timeline.push({ at: existing.last_seen, type: "incident.redelivered", detail: "Duplicate fingerprint suppressed" });
        return { record: existing, created: false };
      }
      const record = createIncidentRecord(incident);
      next.incidents[id] = record;
      return { record, created: true };
    });
  }

  async update(id, mutate) {
    return this.#transaction((next) => {
      const record = next.incidents[id];
      if (!record) throw Object.assign(new Error("incident not found"), { statusCode: 404 });
      mutate(record);
      return record;
    });
  }

  #transaction(mutate) {
    const run = this.writeChain.then(async () => {
      const next = structuredClone(this.data);
      const result = mutate(next);
      await this.#write(next);
      this.data = next;
      return result;
    });
    this.writeChain = run.then(() => undefined, () => undefined);
    return run;
  }

  async #write(next) {
    await mkdir(dirname(this.path), { recursive: true });
    const temporary = `${this.path}.${process.pid}.${Date.now()}.tmp`;
    await writeFile(temporary, `${JSON.stringify(next, null, 2)}\n`, { mode: 0o600 });
    await rename(temporary, this.path);
  }
}
