package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// evaluateRun is deliberately deterministic: unlike an LLM judge, it validates
// the receipts that make this bounded POC safe to hand off. It is a Go
// replacement for the Agent Framework evaluation package, which is not yet
// documented as available for Go.
func evaluateRun(state string) (map[string]any, error) {
	result := map[string]any{"kind": "go-harness-deterministic-evaluation", "result": "FAIL", "criteria": []string{}}
	var run map[string]any
	if err := read(state, "go-harness-run.json", &run); err != nil {
		return result, err
	}
	if run["status"] != "PASS" || run["loop_count"] != float64(1) || run["remediation_started"] != true {
		return result, fmt.Errorf("coordinator terminal receipt is not a single approved PASS")
	}
	criteria := []string{"coordinator PASS after exactly one remediation loop"}
	var remediation map[string]any
	if err := read(state, "remediation-receipt.json", &remediation); err != nil {
		return result, err
	}
	if remediation["state"] != "Succeeded" || remediation["workflow"] == "" {
		return result, fmt.Errorf("no successful named remediation workflow receipt")
	}
	criteria = append(criteria, "approved remediation workflow terminal receipt Succeeded")
	for _, stage := range []string{"summarise", "triage", "health-before", "health-after"} {
		matches, err := filepath.Glob(filepath.Join(state, "go-a2a-"+stage+"-attempt-*-receipt.json"))
		if err != nil || len(matches) == 0 {
			return result, fmt.Errorf("missing %s receipt", stage)
		}
		ok := false
		for _, file := range matches {
			var r receipt
			b, err := os.ReadFile(file)
			if err == nil && json.Unmarshal(b, &r) == nil && r.State == "completed" && r.TerminalText {
				ok = true
			}
		}
		if !ok {
			return result, fmt.Errorf("%s has no successful terminal receipt", stage)
		}
		criteria = append(criteria, stage+" produced a terminal A2A receipt")
	}
	result["result"] = "PASS"
	result["criteria"] = criteria
	result["timestamp"] = now()
	if err := write(state, "go-harness-evaluation.json", result); err != nil {
		return result, err
	}
	return result, nil
}
