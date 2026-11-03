package main

import (
	"encoding/json"
	"net/http"
	"os"
	"time"
)

func main() {
	result := map[string]any{}
	client := &http.Client{Timeout: 2 * time.Second, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse }}
	for i := 1; i+1 < len(os.Args); i += 2 {
		response, err := client.Get(os.Args[i+1])
		if err != nil {
			result[os.Args[i]] = "blocked"
			continue
		}
		result[os.Args[i]] = response.StatusCode
		response.Body.Close()
	}
	json.NewEncoder(os.Stdout).Encode(result)
}
