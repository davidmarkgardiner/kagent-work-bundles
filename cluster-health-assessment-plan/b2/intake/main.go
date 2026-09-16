package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

const maxSnapshotBytes = 256 * 1024
const maxInternalDocumentBytes = 64 * 1024

type server struct {
	db            *pgxpool.Pool
	hmacSecret    []byte
	internalToken string
	bindings      map[string]string
	accepted      atomic.Uint64
	rejected      atomic.Uint64
}

type snapshot struct {
	ClusterID       string         `json:"cluster_id"`
	Generation      string         `json:"source_generation"`
	Sequence        int64          `json:"snapshot_seq"`
	Checksum        string         `json:"checksum"`
	CompletedAt     time.Time      `json:"completed_at"`
	Coverage        map[string]any `json:"coverage"`
	DisplayScore    int            `json:"display_score"`
	Gate            map[string]any `json:"gate"`
	TriageMode      string         `json:"triage_mode"`
	PolicyVersion   string         `json:"policy_version"`
	SerializedBytes int            `json:"serialized_bytes"`
}

type analysisDocument struct {
	ClusterID      string          `json:"cluster_id"`
	Generation     string          `json:"source_generation"`
	Sequence       int64           `json:"snapshot_seq"`
	SourceChecksum string          `json:"source_checksum"`
	Mode           string          `json:"mode"`
	ModelInvoked   bool            `json:"model_invoked"`
	ToolCalls      []any           `json:"tool_calls"`
	Document       json.RawMessage `json:"document"`
}

type summaryDocument struct {
	ClusterID  string          `json:"cluster_id"`
	Generation string          `json:"source_generation"`
	Sequence   int64           `json:"snapshot_seq"`
	Body       json.RawMessage `json:"body"`
}

func env(name string) string {
	v := strings.TrimSpace(os.Getenv(name))
	if v == "" {
		log.Fatalf("%s is required", name)
	}
	return v
}

func parseBindings(raw string) map[string]string {
	out := map[string]string{}
	for _, item := range strings.Split(raw, ",") {
		parts := strings.SplitN(strings.TrimSpace(item), "=", 2)
		if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
			log.Fatalf("invalid ALLOWED_CLUSTER_GENERATIONS entry")
		}
		out[parts[0]] = parts[1]
	}
	return out
}

func databaseURL() string {
	return fmt.Sprintf(
		"postgres://%s:%s@%s:5432/%s?sslmode=disable",
		url.QueryEscape(env("PGUSER")),
		url.QueryEscape(env("PGPASSWORD")),
		env("PGHOST"),
		url.QueryEscape(env("PGDATABASE")),
	)
}

func migrate(ctx context.Context, db *pgxpool.Pool) error {
	_, err := db.Exec(ctx, `
CREATE TABLE IF NOT EXISTS snapshot_attempts (
  cluster_id text NOT NULL,
  generation text NOT NULL,
  sequence bigint NOT NULL,
  checksum text NOT NULL,
  coverage_complete boolean NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  snapshot jsonb NOT NULL,
  PRIMARY KEY (cluster_id, generation, sequence)
);
CREATE TABLE IF NOT EXISTS latest_complete_snapshot (
  cluster_id text PRIMARY KEY,
  generation text NOT NULL,
  sequence bigint NOT NULL,
  checksum text NOT NULL,
  source_completed_at timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  snapshot jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS analyses (
  cluster_id text NOT NULL,
  generation text NOT NULL,
  sequence bigint NOT NULL,
  analysis jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (cluster_id, generation, sequence)
);
CREATE TABLE IF NOT EXISTS summary_issues (
  cluster_id text PRIMARY KEY,
  issue_key text NOT NULL UNIQUE,
  status text NOT NULL,
  revision bigint NOT NULL,
  body jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);`)
	return err
}

func canonicalChecksum(body []byte) (string, error) {
	var document map[string]any
	if err := json.Unmarshal(body, &document); err != nil {
		return "", err
	}
	delete(document, "checksum")
	canonical, err := json.Marshal(document)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(canonical)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

func coverageComplete(s snapshot) bool {
	v, ok := s.Coverage["complete"].(bool)
	return ok && v
}

func (s *server) authenticate(r *http.Request, body []byte) error {
	tsRaw := r.Header.Get("X-Snapshot-Timestamp")
	ts, err := strconv.ParseInt(tsRaw, 10, 64)
	if err != nil || time.Since(time.Unix(ts, 0)) > 5*time.Minute || time.Until(time.Unix(ts, 0)) > time.Minute {
		return errors.New("stale or invalid timestamp")
	}
	provided, err := hex.DecodeString(r.Header.Get("X-Snapshot-Signature"))
	if err != nil {
		return errors.New("invalid signature encoding")
	}
	mac := hmac.New(sha256.New, s.hmacSecret)
	mac.Write([]byte(tsRaw))
	mac.Write([]byte("\n"))
	mac.Write(body)
	if !hmac.Equal(provided, mac.Sum(nil)) {
		return errors.New("signature mismatch")
	}
	return nil
}

func (s *server) ingest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxSnapshotBytes+1))
	if err != nil || len(body) > maxSnapshotBytes {
		s.rejected.Add(1)
		http.Error(w, "snapshot too large", http.StatusRequestEntityTooLarge)
		return
	}
	if err := s.authenticate(r, body); err != nil {
		s.rejected.Add(1)
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	var snap snapshot
	if err := json.Unmarshal(body, &snap); err != nil {
		s.rejected.Add(1)
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}
	if r.Header.Get("X-Cluster-ID") != snap.ClusterID || s.bindings[snap.ClusterID] != snap.Generation {
		s.rejected.Add(1)
		http.Error(w, "cluster or generation not allowlisted", http.StatusForbidden)
		return
	}
	if snap.Sequence < 1 || snap.TriageMode != "report_only" || snap.CompletedAt.IsZero() {
		s.rejected.Add(1)
		http.Error(w, "invalid snapshot contract", http.StatusBadRequest)
		return
	}
	calculated, err := canonicalChecksum(body)
	if err != nil || subtle.ConstantTimeCompare([]byte(calculated), []byte(snap.Checksum)) != 1 {
		s.rejected.Add(1)
		http.Error(w, "checksum mismatch", http.StatusBadRequest)
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	tx, err := s.db.Begin(ctx)
	if err != nil {
		http.Error(w, "store unavailable", http.StatusServiceUnavailable)
		return
	}
	defer tx.Rollback(ctx)
	complete := coverageComplete(snap)
	command, err := tx.Exec(ctx, `INSERT INTO snapshot_attempts
      (cluster_id,generation,sequence,checksum,coverage_complete,snapshot)
      VALUES ($1,$2,$3,$4,$5,$6)
      ON CONFLICT DO NOTHING`, snap.ClusterID, snap.Generation, snap.Sequence, snap.Checksum, complete, body)
	if err != nil {
		http.Error(w, "store unavailable", http.StatusServiceUnavailable)
		return
	}
	if command.RowsAffected() == 0 {
		var existing string
		if err := tx.QueryRow(ctx, `SELECT checksum FROM snapshot_attempts WHERE cluster_id=$1 AND generation=$2 AND sequence=$3`, snap.ClusterID, snap.Generation, snap.Sequence).Scan(&existing); err != nil {
			http.Error(w, "store unavailable", http.StatusServiceUnavailable)
			return
		}
		if existing != snap.Checksum {
			s.rejected.Add(1)
			http.Error(w, "sequence checksum conflict", http.StatusConflict)
			return
		}
	}
	if complete {
		_, err = tx.Exec(ctx, `INSERT INTO latest_complete_snapshot
          (cluster_id,generation,sequence,checksum,source_completed_at,snapshot)
          VALUES ($1,$2,$3,$4,$5,$6)
          ON CONFLICT (cluster_id) DO UPDATE SET
            generation=excluded.generation, sequence=excluded.sequence,
            checksum=excluded.checksum, source_completed_at=excluded.source_completed_at,
            received_at=now(), snapshot=excluded.snapshot
          WHERE latest_complete_snapshot.generation <> excluded.generation
             OR latest_complete_snapshot.sequence < excluded.sequence`,
			snap.ClusterID, snap.Generation, snap.Sequence, snap.Checksum, snap.CompletedAt, body)
		if err != nil {
			http.Error(w, "store unavailable", http.StatusServiceUnavailable)
			return
		}
	}
	if err := tx.Commit(ctx); err != nil {
		http.Error(w, "store unavailable", http.StatusServiceUnavailable)
		return
	}
	s.accepted.Add(1)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"accepted": true, "duplicate": command.RowsAffected() == 0, "sequence": snap.Sequence})
}

func (s *server) latest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !s.internal(r) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	cluster := strings.TrimPrefix(r.URL.Path, "/v1/snapshots/")
	cluster = strings.TrimSuffix(cluster, "/latest")
	if cluster == "" || s.bindings[cluster] == "" {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	var body []byte
	err := s.db.QueryRow(r.Context(), `SELECT snapshot FROM latest_complete_snapshot WHERE cluster_id=$1`, cluster).Scan(&body)
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(body)
}

func (s *server) internal(r *http.Request) bool {
	provided := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	return subtle.ConstantTimeCompare([]byte(provided), []byte(s.internalToken)) == 1
}

func readBoundedJSON(w http.ResponseWriter, r *http.Request, target any) ([]byte, error) {
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxInternalDocumentBytes+1))
	if err != nil || len(body) > maxInternalDocumentBytes {
		return nil, errors.New("document too large")
	}
	if err := json.Unmarshal(body, target); err != nil {
		return nil, errors.New("invalid JSON")
	}
	return body, nil
}

func (s *server) analyses(w http.ResponseWriter, r *http.Request) {
	if !s.internal(r) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	if r.Method == http.MethodGet {
		cluster := strings.TrimPrefix(r.URL.Path, "/v1/analyses/")
		cluster = strings.TrimSuffix(cluster, "/latest")
		var body []byte
		err := s.db.QueryRow(r.Context(), `SELECT analysis FROM analyses WHERE cluster_id=$1 ORDER BY sequence DESC LIMIT 1`, cluster).Scan(&body)
		if err != nil {
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write(body)
		return
	}
	if r.Method != http.MethodPost || r.URL.Path != "/v1/analyses" {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var analysis analysisDocument
	body, err := readBoundedJSON(w, r, &analysis)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if analysis.ClusterID == "" || analysis.Generation == "" || analysis.Sequence < 1 || analysis.SourceChecksum == "" || analysis.Mode == "" || len(analysis.Document) == 0 || len(analysis.ToolCalls) != 0 {
		http.Error(w, "invalid analysis contract", http.StatusBadRequest)
		return
	}
	var exists bool
	err = s.db.QueryRow(r.Context(), `SELECT EXISTS(SELECT 1 FROM latest_complete_snapshot WHERE cluster_id=$1 AND generation=$2 AND sequence=$3 AND checksum=$4)`, analysis.ClusterID, analysis.Generation, analysis.Sequence, analysis.SourceChecksum).Scan(&exists)
	if err != nil || !exists {
		http.Error(w, "source snapshot is not current", http.StatusConflict)
		return
	}
	command, err := s.db.Exec(r.Context(), `INSERT INTO analyses(cluster_id,generation,sequence,analysis) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING`, analysis.ClusterID, analysis.Generation, analysis.Sequence, body)
	if err != nil {
		http.Error(w, "store unavailable", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"accepted": true, "duplicate": command.RowsAffected() == 0, "sequence": analysis.Sequence})
}

func (s *server) summaries(w http.ResponseWriter, r *http.Request) {
	if !s.internal(r) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	if r.Method == http.MethodGet {
		cluster := strings.TrimPrefix(r.URL.Path, "/v1/summaries/")
		cluster = strings.TrimSuffix(cluster, "/latest")
		var issueKey, status string
		var revision int64
		var body []byte
		err := s.db.QueryRow(r.Context(), `SELECT issue_key,status,revision,body FROM summary_issues WHERE cluster_id=$1`, cluster).Scan(&issueKey, &status, &revision, &body)
		if err != nil {
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"cluster_id": cluster, "issue_key": issueKey, "status": status, "revision": revision, "body": json.RawMessage(body)})
		return
	}
	if r.Method != http.MethodPost || r.URL.Path != "/v1/summaries" {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var summary summaryDocument
	body, err := readBoundedJSON(w, r, &summary)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if summary.ClusterID == "" || summary.Generation == "" || summary.Sequence < 1 || len(summary.Body) == 0 {
		http.Error(w, "invalid summary contract", http.StatusBadRequest)
		return
	}
	var exists bool
	err = s.db.QueryRow(r.Context(), `SELECT EXISTS(SELECT 1 FROM analyses WHERE cluster_id=$1 AND generation=$2 AND sequence=$3)`, summary.ClusterID, summary.Generation, summary.Sequence).Scan(&exists)
	if err != nil || !exists {
		http.Error(w, "analysis not found", http.StatusConflict)
		return
	}
	issueKey := "cluster-health/" + summary.ClusterID
	tx, err := s.db.Begin(r.Context())
	if err != nil {
		http.Error(w, "store unavailable", http.StatusServiceUnavailable)
		return
	}
	defer tx.Rollback(r.Context())
	command, err := tx.Exec(r.Context(), `INSERT INTO summary_issues(cluster_id,issue_key,status,revision,body) VALUES($1,$2,'open',1,$3) ON CONFLICT DO NOTHING`, summary.ClusterID, issueKey, body)
	if err != nil {
		http.Error(w, "store unavailable", http.StatusServiceUnavailable)
		return
	}
	action := "created"
	var revision int64 = 1
	if command.RowsAffected() == 0 {
		var status string
		var unchanged bool
		if err := tx.QueryRow(r.Context(), `SELECT status,revision,body = $2::jsonb FROM summary_issues WHERE cluster_id=$1 FOR UPDATE`, summary.ClusterID, string(body)).Scan(&status, &revision, &unchanged); err != nil {
			http.Error(w, "store unavailable", http.StatusServiceUnavailable)
			return
		}
		if status != "open" {
			http.Error(w, "summary is not open; automatic replacement blocked", http.StatusConflict)
			return
		}
		if unchanged {
			action = "unchanged"
		} else {
			revision++
			if _, err := tx.Exec(r.Context(), `UPDATE summary_issues SET revision=$2,body=$3,updated_at=now() WHERE cluster_id=$1`, summary.ClusterID, revision, body); err != nil {
				http.Error(w, "store unavailable", http.StatusServiceUnavailable)
				return
			}
			action = "updated"
		}
	}
	if err := tx.Commit(r.Context()); err != nil {
		http.Error(w, "store unavailable", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"accepted": true, "action": action, "issue_key": issueKey, "revision": revision})
}

func (s *server) metrics(w http.ResponseWriter, _ *http.Request) {
	fmt.Fprintf(w, "# TYPE cluster_health_intake_accepted_total counter\ncluster_health_intake_accepted_total %d\n", s.accepted.Load())
	fmt.Fprintf(w, "# TYPE cluster_health_intake_rejected_total counter\ncluster_health_intake_rejected_total %d\n", s.rejected.Load())
}

func main() {
	ctx := context.Background()
	var db *pgxpool.Pool
	var err error
	for attempt := 0; attempt < 30; attempt++ {
		db, err = pgxpool.New(ctx, databaseURL())
		if err == nil {
			err = db.Ping(ctx)
		}
		if err == nil {
			break
		}
		time.Sleep(2 * time.Second)
	}
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	if err := migrate(ctx, db); err != nil {
		log.Fatal(err)
	}
	s := &server{db: db, hmacSecret: []byte(env("HMAC_SECRET")), internalToken: env("INTERNAL_TOKEN"), bindings: parseBindings(env("ALLOWED_CLUSTER_GENERATIONS"))}
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) { io.WriteString(w, "ok\n") })
	mux.HandleFunc("/metrics", s.metrics)
	mux.HandleFunc("/v1/snapshots", s.ingest)
	mux.HandleFunc("/v1/snapshots/", s.latest)
	mux.HandleFunc("/v1/analyses", s.analyses)
	mux.HandleFunc("/v1/analyses/", s.analyses)
	mux.HandleFunc("/v1/summaries", s.summaries)
	mux.HandleFunc("/v1/summaries/", s.summaries)
	server := &http.Server{Addr: ":8443", Handler: mux, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 30 * time.Second}
	log.Fatal(server.ListenAndServeTLS(env("TLS_CERT_FILE"), env("TLS_KEY_FILE")))
}
