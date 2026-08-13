// Go Harness coordinator POC.
//
// It keeps the execution boundary deliberately narrow: the coordinator only
// invokes fixed kagent A2A agents and persists receipts. A separately approved
// remediation workflow is represented by a terminal receipt; this process has
// no Kubernetes credentials and cannot change cluster resources.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type stage struct{ Name, Agent, Prompt string }
type receipt struct {
	Stage, Agent, State string `json:"stage,omitempty" json:"agent,omitempty" json:"state"`
	HTTPStatus          int    `json:"http_status,omitempty"`
	TerminalText        bool   `json:"terminal_text_present"`
	Timestamp           string `json:"timestamp"`
}

func main() {
	if err := run(context.Background()); err != nil {
		panic(err)
	}
}

func run(ctx context.Context) error {
	state := getenv("STATE_DIR", "/state")
	mode := getenv("MODE", "request")
	request := getenv("POC_REQUEST", "Synthetic healthcheck POC only.")
	if mode == "request" {
		return write(state, "go-harness-run.json", map[string]any{"status": "awaiting-approval", "request": request, "tool_invoked": false, "timestamp": now()})
	}
	if mode == "deny" {
		return write(state, "go-harness-run.json", map[string]any{"status": "DENIED", "request": request, "remediation_started": false, "timestamp": now()})
	}
	if mode != "approve" {
		return errors.New("MODE must be request, deny, or approve")
	}
	prior := map[string]any{}
	if err := read(state, "go-harness-run.json", &prior); err != nil {
		return fmt.Errorf("approval needs prior request: %w", err)
	}
	if prior["status"] != "awaiting-approval" {
		return errors.New("refusing approval: no awaiting request")
	}

	base := strings.TrimSuffix(os.Getenv("KAGENT_A2A_BASE_URL"), "/")
	if base == "" {
		return errors.New("KAGENT_A2A_BASE_URL is required")
	}
	stages := []stage{
		{"summarise", getenv("ISSUE_SUMMARISER_AGENT", "maf-go-issue-summariser"), request},
		{"triage", getenv("SRE_TRIAGE_AGENT", "maf-go-sre-triage"), "Triage this synthetic incident:\n" + request},
		{"health-before", getenv("UK8S_HEALTHCHECK_AGENT", "maf-go-uk8s-healthcheck"), "BASELINE: perform the synthetic POC health check."},
	}
	for _, s := range stages {
		if err := call(ctx, base, state, s); err != nil {
			return terminal(state, "BLOCKED", err)
		}
	}
	// Remediation is an external, explicitly-approved workflow receipt. The
	// coordinator cannot launch it itself; an operator/workflow runner must put
	// remediation-receipt.json in the durable state volume.
	var remediation map[string]any
	if err := read(state, "remediation-receipt.json", &remediation); err != nil {
		return terminal(state, "BLOCKED", errors.New("approved remediation receipt is required"))
	}
	if remediation["state"] != "Succeeded" {
		return terminal(state, "FAIL", errors.New("remediation did not succeed"))
	}
	if err := call(ctx, base, state, stage{"health-after", getenv("UK8S_HEALTHCHECK_AGENT", "maf-go-uk8s-healthcheck"), "POST_REMEDIATION: perform the synthetic POC health check."}); err != nil {
		return terminal(state, "FAIL", err)
	}
	return write(state, "go-harness-run.json", map[string]any{"status": "PASS", "request": request, "remediation_started": true, "loop_count": 1, "timestamp": now()})
}

func call(ctx context.Context, base, state string, s stage) error {
	p := map[string]any{"jsonrpc": "2.0", "id": "go-harness-" + s.Name, "method": "message/send", "params": map[string]any{"message": map[string]any{"kind": "message", "messageId": "go-harness-" + s.Name, "contextId": "go-harness-" + s.Name, "role": "user", "parts": []map[string]string{{"kind": "text", "text": s.Prompt}}}}}
	b, _ := json.Marshal(p)
	req, _ := http.NewRequestWithContext(ctx, http.MethodPost, base+"/"+s.Agent+"/", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	c := &http.Client{Timeout: 120 * time.Second}
	resp, err := c.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	var data map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&data)
	text := fmt.Sprint(data["result"])
	r := receipt{Stage: s.Name, Agent: s.Agent, State: "completed", HTTPStatus: resp.StatusCode, TerminalText: resp.StatusCode == 200 && text != "map[]", Timestamp: now()}
	if err := write(state, "go-a2a-"+s.Name+"-receipt.json", r); err != nil {
		return err
	}
	if !r.TerminalText {
		return fmt.Errorf("%s returned no terminal response", s.Name)
	}
	return nil
}

func terminal(state, status string, err error) error {
	_ = write(state, "go-harness-run.json", map[string]any{"status": status, "error": err.Error(), "timestamp": now()})
	return err
}
func now() string { return time.Now().UTC().Format(time.RFC3339) }
func getenv(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}
func write(dir, name string, v any) error {
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	b, e := json.MarshalIndent(v, "", "  ")
	if e != nil {
		return e
	}
	return os.WriteFile(filepath.Join(dir, name), append(b, '\n'), 0600)
}
func read(dir, name string, v any) error {
	b, e := os.ReadFile(filepath.Join(dir, name))
	if e != nil {
		return e
	}
	return json.Unmarshal(b, v)
}
