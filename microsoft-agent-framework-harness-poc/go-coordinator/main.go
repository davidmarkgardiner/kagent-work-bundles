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

type stage struct {
	Name, Agent, Prompt string
	Attempt             int
	FallbackFrom        string
}
type receipt struct {
	Stage           string `json:"stage,omitempty"`
	Agent           string `json:"agent,omitempty"`
	State           string `json:"state"`
	HTTPStatus      int    `json:"http_status,omitempty"`
	TerminalText    bool   `json:"terminal_text_present"`
	Attempt         int    `json:"attempt"`
	FallbackFrom    string `json:"fallback_from,omitempty"`
	ResponseExcerpt string `json:"response_excerpt,omitempty"`
	Error           string `json:"error,omitempty"`
	Timestamp       string `json:"timestamp"`
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
	if mode == "evaluate" {
		result, err := evaluateRun(state)
		if err != nil {
			_ = write(state, "go-harness-evaluation.json", map[string]any{"kind": "go-harness-deterministic-evaluation", "result": "FAIL", "error": err.Error(), "timestamp": now()})
			return err
		}
		fmt.Printf("evaluation=%s criteria=%d\n", result["result"], len(result["criteria"].([]string)))
		return nil
	}
	if mode != "approve" {
		return errors.New("MODE must be request, deny, approve, or evaluate")
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
		{Name: "summarise", Agent: getenv("ISSUE_SUMMARISER_AGENT", "maf-go-issue-summariser"), Prompt: request},
		{Name: "triage", Agent: getenv("SRE_TRIAGE_AGENT", "maf-go-sre-triage"), Prompt: "Triage this synthetic incident:\n" + request},
		{Name: "health-before", Agent: getenv("UK8S_HEALTHCHECK_AGENT", "maf-go-uk8s-healthcheck"), Prompt: "BASELINE: perform the synthetic POC health check."},
	}
	for _, s := range stages {
		if err := callWithRetry(ctx, base, state, s); err != nil {
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
	if err := callWithRetry(ctx, base, state, stage{Name: "health-after", Agent: getenv("UK8S_HEALTHCHECK_AGENT", "maf-go-uk8s-healthcheck"), Prompt: "POST_REMEDIATION: perform the synthetic POC health check."}); err != nil {
		return terminal(state, "FAIL", err)
	}
	return write(state, "go-harness-run.json", map[string]any{"status": "PASS", "request": request, "remediation_started": true, "loop_count": 1, "timestamp": now()})
}

// callWithRetry provides the Go replacement for unavailable packaged looping:
// one retry of the same agent, then one explicitly configured equivalent
// fallback. Every failed attempt remains a receipt; no remediation is retried.
func callWithRetry(ctx context.Context, base, state string, s stage) error {
	var last error
	for attempt := 1; attempt <= 2; attempt++ {
		s.Attempt = attempt
		if err := call(ctx, base, state, s); err == nil {
			return nil
		} else {
			last = err
		}
	}
	fallback := os.Getenv(strings.ToUpper(strings.ReplaceAll(s.Name, "-", "_")) + "_FALLBACK_AGENT")
	if fallback != "" && fallback != s.Agent {
		original := s.Agent
		s.Agent = fallback
		s.Attempt = 3
		s.FallbackFrom = original
		if err := call(ctx, base, state, s); err == nil {
			return nil
		} else {
			last = err
		}
	}
	return fmt.Errorf("%s circuit-breaker opened after retry/fallback: %w", s.Name, last)
}

func call(ctx context.Context, base, state string, s stage) error {
	if s.Attempt == 0 {
		s.Attempt = 1
	}
	requestID := fmt.Sprintf("go-harness-%s-attempt-%d", s.Name, s.Attempt)
	p := map[string]any{"jsonrpc": "2.0", "id": requestID, "method": "message/send", "params": map[string]any{"message": map[string]any{"kind": "message", "messageId": requestID, "contextId": requestID, "role": "user", "parts": []map[string]string{{"kind": "text", "text": s.Prompt}}}}}
	b, _ := json.Marshal(p)
	req, _ := http.NewRequestWithContext(ctx, http.MethodPost, base+"/"+s.Agent+"/", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	c := &http.Client{Timeout: 120 * time.Second}
	resp, err := c.Do(req)
	if err != nil {
		_ = write(state, receiptName(s), receipt{Stage: s.Name, Agent: s.Agent, State: "failed", Attempt: s.Attempt, FallbackFrom: s.FallbackFrom, Error: err.Error(), Timestamp: now()})
		return err
	}
	defer resp.Body.Close()
	var data map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&data)
	text := fmt.Sprint(data["result"])
	r := receipt{Stage: s.Name, Agent: s.Agent, State: "completed", HTTPStatus: resp.StatusCode, TerminalText: resp.StatusCode == 200 && text != "map[]", Attempt: s.Attempt, FallbackFrom: s.FallbackFrom, ResponseExcerpt: responseExcerpt(text), Timestamp: now()}
	if !r.TerminalText {
		r.State = "failed"
		r.Error = fmt.Sprintf("unexpected HTTP status or missing terminal response: %d", resp.StatusCode)
	}
	if err := write(state, receiptName(s), r); err != nil {
		return err
	}
	if !r.TerminalText {
		return fmt.Errorf("%s returned no terminal response", s.Name)
	}
	return nil
}

func receiptName(s stage) string {
	return fmt.Sprintf("go-a2a-%s-attempt-%d-receipt.json", s.Name, s.Attempt)
}

func clip(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max] + "..."
}

// Agent output can contain incident or business data. Store it only in the
// explicitly opted-in lab diagnostic mode; terminal status remains observable.
func responseExcerpt(s string) string {
	if os.Getenv("RECORD_RESPONSE_EXCERPT") != "true" {
		return ""
	}
	return clip(s, 400)
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
