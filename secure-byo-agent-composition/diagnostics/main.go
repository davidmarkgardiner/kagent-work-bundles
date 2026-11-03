package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

const taskMethod = "/kagent.runtime.v1.TaskStoreService/GetTask"
const publicMethod = "/kagent.api.v1.SessionService/ListSessions"

var sessionID = regexp.MustCompile(`^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$`)

type rawCodec struct{}

func (rawCodec) Name() string { return "proto" }
func (rawCodec) Marshal(v any) ([]byte, error) {
	b, ok := v.(*[]byte)
	if !ok {
		return nil, fmt.Errorf("invalid request")
	}
	return *b, nil
}
func (rawCodec) Unmarshal(b []byte, v any) error {
	p, ok := v.(*[]byte)
	if !ok {
		return fmt.Errorf("invalid response")
	}
	*p = append((*p)[:0], b...)
	return nil
}

func field(number byte, s string) []byte {
	b := []byte{number<<3 | 2}
	n := len(s)
	for n >= 128 {
		b = append(b, byte(n)|0x80)
		n >>= 7
	}
	b = append(b, byte(n))
	return append(b, []byte(s)...)
}
func getTask(session string) []byte {
	return append(field(1, session), field(2, "secure-byo-probe-nonexistent-task")...)
}
func internalAuthority(target string, outside bool) bool {
	host, port, err := net.SplitHostPort(target)
	if err != nil || port == "" {
		return false
	}
	return strings.HasSuffix(host, ".svc.cluster.local") && !strings.ContainsAny(host, "@/ ?#") && port == "8084" || outside && (host == "127.0.0.1" || host == "localhost")
}
func validURL(raw string, outside bool) bool {
	u, e := url.Parse(raw)
	return e == nil && u.Scheme == "http" && u.User == nil && u.RawQuery == "" && u.Fragment == "" && (strings.HasSuffix(u.Hostname(), ".svc.cluster.local") || outside && (u.Hostname() == "127.0.0.1" || u.Hostname() == "localhost"))
}
func rpc(conn *grpc.ClientConn, method, session, authorization string) codes.Code {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if authorization != "" {
		ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs("authorization", authorization))
	}
	request := []byte{}
	if method == taskMethod {
		request = getTask(session)
	}
	var response []byte
	err := conn.Invoke(ctx, method, &request, &response, grpc.ForceCodec(rawCodec{}), grpc.MaxCallRecvMsgSize(65536), grpc.MaxCallSendMsgSize(1024))
	return status.Code(err)
}
func httpProbe(raw string) any {
	client := &http.Client{Timeout: 2 * time.Second, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse }}
	r, e := client.Get(raw)
	if e != nil {
		return "blocked"
	}
	defer r.Body.Close()
	return r.StatusCode
}

type check struct {
	Name     string `json:"name"`
	Observed any    `json:"observed"`
	Expected any    `json:"expected"`
	Passed   bool   `json:"passed"`
}

func main() {
	bridge := flag.String("bridge", "", "Fixed runtime bridge DNS:port")
	own := flag.String("own-session", "", "Current actor session UUID")
	sibling := flag.String("sibling-session", "", "Different session UUID used only for a denied read")
	outside := flag.Bool("outside", false, "Run public/forged identity checks outside an actor")
	anonymousCode := flag.String("anonymous-code", "PermissionDenied", "Expected denial for the configured native user auth mode: PermissionDenied or Unauthenticated")
	direct := flag.String("direct-controller", "", "Original controller HTTP URL")
	dedicated := flag.String("dedicated-controller", "", "Dedicated POC controller HTTP URL")
	model := flag.String("direct-model", "", "Upstream model HTTP URL")
	gateway := flag.String("gateway", "", "Approved gateway HTTP URL without credentials")
	flag.Parse()
	if !internalAuthority(*bridge, *outside) || !sessionID.MatchString(*own) || !sessionID.MatchString(*sibling) || *own == *sibling {
		fmt.Fprintln(os.Stderr, "invalid fixed probe scope")
		os.Exit(2)
	}
	for _, u := range []string{*direct, *dedicated, *model, *gateway} {
		if u != "" && !validURL(u, *outside) {
			fmt.Fprintln(os.Stderr, "invalid probe URL")
			os.Exit(2)
		}
	}
	if *anonymousCode != "PermissionDenied" && *anonymousCode != "Unauthenticated" {
		fmt.Fprintln(os.Stderr, "invalid anonymous denial code")
		os.Exit(2)
	}
	conn, err := grpc.NewClient("passthrough:///"+*bridge, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		fmt.Fprintln(os.Stderr, "cannot create diagnostic transport")
		os.Exit(2)
	}
	defer conn.Close()
	results := []check{}
	add := func(name string, observed, expected any) {
		results = append(results, check{name, observed, expected, observed == expected})
	}
	if *outside {
		// The native insecure user provider identifies absent/opaque credentials as users;
		// private runtime methods still require an actor and return PermissionDenied.
		add("anonymous-runtime", rpc(conn, taskMethod, *own, "").String(), *anonymousCode)
		add("uninjected-placeholder", rpc(conn, taskMethod, *own, "Bearer placeholder").String(), *anonymousCode)
		token := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"none","typ":"JWT"}`)) + "." + base64.RawURLEncoding.EncodeToString([]byte(`{"actor.ate.dev":{},"iss":"https://idp.ate-system.svc"}`)) + "."
		add("forged-actor", rpc(conn, taskMethod, *own, "Bearer "+token).String(), codes.Unauthenticated.String())
	} else {
		// This is the same placeholder contract used by native ADK controllerclient.
		// Substrate injects the current actor token at the approved runtime origin.
		add("own-session-read", rpc(conn, taskMethod, *own, "Bearer placeholder").String(), codes.NotFound.String())
		add("sibling-session-read", rpc(conn, taskMethod, *sibling, "Bearer placeholder").String(), codes.PermissionDenied.String())
	}
	add("management-rpc-not-routed", rpc(conn, publicMethod, *own, "Bearer placeholder").String(), codes.Unimplemented.String())
	if *direct != "" {
		add("direct-controller", httpProbe(*direct), "blocked")
	}
	if *dedicated != "" {
		add("dedicated-controller", httpProbe(*dedicated), "blocked")
	}
	if *model != "" {
		add("direct-model", httpProbe(*model), "blocked")
	}
	if *gateway != "" {
		add("reachable-authenticated-gateway", httpProbe(*gateway), http.StatusUnauthorized)
	}
	passed := true
	for _, r := range results {
		passed = passed && r.Passed
	}
	json.NewEncoder(os.Stdout).Encode(map[string]any{"passed": passed, "checks": results, "mode": map[bool]string{true: "outside", false: "actor"}[*outside]})
	if !passed {
		os.Exit(1)
	}
}
