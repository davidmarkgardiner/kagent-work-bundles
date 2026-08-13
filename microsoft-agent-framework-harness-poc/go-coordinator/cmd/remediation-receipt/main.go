// remediation-receipt is intentionally separate from the Harness coordinator.
// In the POC it represents the terminal receipt emitted by an approval-gated,
// least-privilege remediation workflow. It performs no Kubernetes action.
package main

import (
	"encoding/json"
	"os"
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
	b, err := json.MarshalIndent(map[string]string{
		"state": "Succeeded", "kind": "synthetic-approved-remediation-receipt",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "remediation-receipt.json"), append(b, '\n'), 0600); err != nil {
		panic(err)
	}
}
