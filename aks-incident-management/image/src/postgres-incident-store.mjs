import pg from "pg";
import { addTimeline, createIncidentRecord, incidentIdFor } from "./workflow.mjs";

const { Pool } = pg;

export class PostgresIncidentStore {
  description = "PostgreSQL incident ledger with transactional fingerprint claims";

  constructor(options = {}) {
    this.pool = options.pool ?? new Pool(options.connectionString ? { connectionString: options.connectionString } : undefined);
    this.pool.on?.("error", (error) => console.error("idle PostgreSQL connection failed; the pool will reconnect", error.message));
  }

  async load() {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS incident_records (
        id text PRIMARY KEY,
        fingerprint text NOT NULL UNIQUE,
        record jsonb NOT NULL,
        version bigint NOT NULL DEFAULT 1,
        updated_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE INDEX IF NOT EXISTS incident_records_updated_idx ON incident_records (updated_at DESC);
      CREATE TABLE IF NOT EXISTS incident_audit (
        sequence bigserial PRIMARY KEY,
        incident_id text NOT NULL REFERENCES incident_records(id) ON DELETE CASCADE,
        event_type text NOT NULL,
        detail text NOT NULL,
        occurred_at timestamptz NOT NULL
      );
      CREATE INDEX IF NOT EXISTS incident_audit_incident_idx ON incident_audit (incident_id, sequence);
    `);
    return this;
  }

  async list() {
    const result = await this.pool.query("SELECT record FROM incident_records ORDER BY updated_at DESC");
    return result.rows.map((row) => row.record);
  }

  async get(id) {
    const result = await this.pool.query("SELECT record FROM incident_records WHERE id = $1", [id]);
    return result.rows[0]?.record ?? null;
  }

  async upsert(incident) {
    const id = incidentIdFor(incident.fingerprint);
    return this.#transaction(async (client) => {
      await client.query("SELECT pg_advisory_xact_lock(hashtext($1))", [id]);
      const selected = await client.query("SELECT record FROM incident_records WHERE id = $1 FOR UPDATE", [id]);
      if (selected.rowCount) {
        const record = selected.rows[0].record;
        record.delivery_count += 1;
        addTimeline(record, "incident.redelivered", "Duplicate fingerprint suppressed");
        await client.query("UPDATE incident_records SET record = $2, version = version + 1, updated_at = now() WHERE id = $1", [id, record]);
        await this.#appendAudit(client, id, record.timeline.at(-1));
        return { record, created: false };
      }
      const record = createIncidentRecord(incident);
      await client.query("INSERT INTO incident_records (id, fingerprint, record) VALUES ($1, $2, $3)", [id, incident.fingerprint, record]);
      await this.#appendAudit(client, id, record.timeline[0]);
      return { record, created: true };
    });
  }

  async update(id, mutate) {
    return this.#transaction(async (client) => {
      const selected = await client.query("SELECT record FROM incident_records WHERE id = $1 FOR UPDATE", [id]);
      if (!selected.rowCount) throw Object.assign(new Error("incident not found"), { statusCode: 404 });
      const record = selected.rows[0].record;
      const priorTimelineLength = record.timeline.length;
      mutate(record);
      await client.query("UPDATE incident_records SET record = $2, version = version + 1, updated_at = now() WHERE id = $1", [id, record]);
      for (const event of record.timeline.slice(priorTimelineLength)) await this.#appendAudit(client, id, event);
      return record;
    });
  }

  async close() {
    await this.pool.end();
  }

  async #appendAudit(client, id, event) {
    await client.query("INSERT INTO incident_audit (incident_id, event_type, detail, occurred_at) VALUES ($1, $2, $3, $4)", [id, event.type, event.detail, event.at]);
  }

  async #transaction(operation) {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const result = await operation(client);
      await client.query("COMMIT");
      return result;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }
}
