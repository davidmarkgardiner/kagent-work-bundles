package main

import "testing"

func TestEvaluateRunPassesCompleteBoundedReceiptSet(t *testing.T) {
	dir := t.TempDir()
	if err := write(dir, "go-harness-run.json", map[string]any{"status": "PASS", "loop_count": 1, "remediation_started": true}); err != nil {
		t.Fatal(err)
	}
	if err := write(dir, "remediation-receipt.json", map[string]any{"state": "Succeeded", "workflow": "test-workflow"}); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"summarise", "triage", "health-before", "health-after"} {
		if err := write(dir, "go-a2a-"+name+"-attempt-1-receipt.json", receipt{State: "completed", TerminalText: true}); err != nil {
			t.Fatal(err)
		}
	}
	result, err := evaluateRun(dir)
	if err != nil || result["result"] != "PASS" {
		t.Fatalf("result=%v err=%v", result, err)
	}
}

func TestEvaluateRunRejectsRepeatedOrUnapprovedWork(t *testing.T) {
	dir := t.TempDir()
	if err := write(dir, "go-harness-run.json", map[string]any{"status": "PASS", "loop_count": 2, "remediation_started": true}); err != nil {
		t.Fatal(err)
	}
	if _, err := evaluateRun(dir); err == nil {
		t.Fatal("expected evaluation to reject repeated remediation")
	}
}

func TestResponseExcerptIsOptIn(t *testing.T) {
	t.Setenv("RECORD_RESPONSE_EXCERPT", "")
	if got := responseExcerpt("private result"); got != "" {
		t.Fatalf("excerpt should be disabled by default, got %q", got)
	}
	t.Setenv("RECORD_RESPONSE_EXCERPT", "true")
	if got := responseExcerpt("diagnostic result"); got != "diagnostic result" {
		t.Fatalf("expected opted-in excerpt, got %q", got)
	}
}
