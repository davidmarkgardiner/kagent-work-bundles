package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"time"

	a2atype "github.com/a2aproject/a2a-go/v2/a2a"
	"github.com/a2aproject/a2a-go/v2/a2asrv"
	"github.com/a2aproject/a2a-go/v2/a2asrv/limiter"
	"github.com/kagent-dev/kagent/go/adk/pkg/a2a"
	"github.com/kagent-dev/kagent/go/adk/pkg/a2a/server"
	runnerpkg "github.com/kagent-dev/kagent/go/adk/pkg/runner"
	"github.com/kagent-dev/kagent/go/adk/pkg/telemetry"
	"github.com/kagent-dev/kagent/go/api/adk"
	"github.com/kagent-dev/kagent/go/pkg/logging"
	"github.com/kagent-dev/kagent/go/pkg/tracing"
	adksession "google.golang.org/adk/v2/session"
)

func main() {
	if err := run(); err != nil {
		slog.Error("standalone agent stopped", "error", err)
		os.Exit(1)
	}
}

func run() error {
	logger, err := logging.New(os.Stderr, "info")
	if err != nil {
		return err
	}
	slog.SetDefault(logger)
	data, err := os.ReadFile("/config/agent.json")
	if err != nil {
		return err
	}
	var config adk.AgentConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return err
	}
	if config.Model == nil || config.Memory != nil || config.SessionDBURL != "" || len(config.StdioTools) != 0 || config.AgentPlugins != nil || config.SkillsDirectory != "" || len(config.RemoteAgents) != 0 || len(config.SubAgents) != 0 {
		return fmt.Errorf("standalone demo requires a model, in-memory sessions, and remote read-only tools only")
	}
	identity := tracing.RuntimeTelemetry{Runtime: tracing.RuntimeADKGo, AgentName: "flow-standalone-kagent", AgentNamespace: os.Getenv("POD_NAMESPACE")}
	providers, err := telemetry.Init(context.Background(), identity)
	if err != nil {
		return err
	}
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = providers.Shutdown(ctx)
	}()
	ctx := logging.IntoContext(context.Background(), logger)
	sessions := adksession.InMemoryService()
	runnerConfig, err := runnerpkg.CreateRunnerConfig(ctx, &config, sessions, "flow-standalone-kagent", nil, nil)
	if err != nil {
		return err
	}
	executor, err := a2a.NewKAgentExecutor(a2a.KAgentExecutorConfig{RunnerConfig: runnerConfig, SessionService: sessions, AppName: "flow-standalone-kagent", Logger: logger, Flush: providers.ForceFlush})
	if err != nil {
		return err
	}
	card := a2atype.AgentCard{Name: "flow-standalone-kagent", Description: "Native kagent ADK in a normal Kubernetes Deployment without Substrate", Version: "1.0.0-alpha8", SupportedInterfaces: []*a2atype.AgentInterface{a2atype.NewAgentInterface("/", a2atype.TransportProtocolJSONRPC)}, DefaultInputModes: []string{"text/plain"}, DefaultOutputModes: []string{"text/plain"}}
	service, err := server.NewA2AServer(card, executor, logger, server.ServerConfig{Port: "8080", ShutdownTimeout: 5 * time.Second, Telemetry: identity, Flush: providers.ForceFlush}, a2asrv.WithConcurrencyConfig(limiter.ConcurrencyConfig{MaxExecutions: 1}), a2asrv.WithCallInterceptors(a2a.UserIDCallInterceptor()))
	if err != nil {
		return err
	}
	return service.Run()
}
