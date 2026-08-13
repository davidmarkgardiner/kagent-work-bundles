// remediation-receipt is intentionally separate from the Harness coordinator.
// In the POC it represents the terminal receipt emitted by an approval-gated,
// least-privilege remediation workflow. It performs no Kubernetes action.
package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

func main() {
	dir := os.Getenv("STATE_DIR")
	if dir == "" {
		dir = "/state"
	}
	if err := os.MkdirAll(dir, 0700); err != nil {
		panic(err)
	}
	workflow := os.Getenv("WORKFLOW_NAME")
	if workflow == "" {
		panic("WORKFLOW_NAME is required")
	}
	ns := os.Getenv("WORKFLOW_NAMESPACE")
	if ns == "" {
		ns = "test-remediation"
	}
	phaseBytes, err := exec.Command("kubectl", "-n", ns, "get", "workflow", workflow, "-o", "jsonpath={.status.phase}").Output()
	if err != nil {
		panic(err)
	}
	phase := string(phaseBytes)
	b, err := json.MarshalIndent(map[string]string{
		"state": phase, "kind": "argo-workflow-terminal-receipt", "workflow": workflow,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "remediation-receipt.json"), append(b, '\n'), 0600); err != nil {
		panic(err)
	}
}
