package main

import (
	"context"
	"net"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/encoding/protowire"
)

func TestWireRequestAndStatus(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	server := grpc.NewServer(grpc.ForceServerCodec(rawCodec{}))
	server.RegisterService(&grpc.ServiceDesc{ServiceName: "kagent.runtime.v1.TaskStoreService", HandlerType: (*interface{})(nil), Methods: []grpc.MethodDesc{{MethodName: "GetTask", Handler: func(_ any, ctx context.Context, decode func(any) error, _ grpc.UnaryServerInterceptor) (any, error) {
		var request []byte
		if err := decode(&request); err != nil {
			return nil, err
		}
		number, typ, n := protowire.ConsumeTag(request)
		if n < 0 || number != 1 || typ != protowire.BytesType {
			return nil, status.Error(codes.InvalidArgument, "invalid session field")
		}
		own, n2 := protowire.ConsumeString(request[n:])
		if n2 < 0 || own != "abc" {
			return nil, status.Error(codes.InvalidArgument, "invalid session value")
		}
		rest := request[n+n2:]
		number, typ, n = protowire.ConsumeTag(rest)
		if n < 0 || number != 2 || typ != protowire.BytesType {
			return nil, status.Error(codes.InvalidArgument, "invalid task field")
		}
		task, n2 := protowire.ConsumeString(rest[n:])
		if n2 < 0 || task != "secure-byo-probe-nonexistent-task" || n+n2 != len(rest) {
			return nil, status.Error(codes.InvalidArgument, "invalid task scope")
		}

		md, _ := metadata.FromIncomingContext(ctx)
		if len(md.Get("authorization")) == 0 {
			return nil, status.Error(codes.PermissionDenied, "actor required")
		}
		return nil, status.Error(codes.NotFound, "known missing task")
	}}}}, struct{}{})
	go server.Serve(listener)
	defer server.Stop()
	conn, err := grpc.NewClient(listener.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	if got := rpc(conn, taskMethod, "abc", "Bearer placeholder"); got != codes.NotFound {
		t.Fatalf("got %v", got)
	}
	if got := rpc(conn, taskMethod, "abc", ""); got != codes.PermissionDenied {
		t.Fatalf("got %v", got)
	}
	if got := rpc(conn, publicMethod, "abc", "Bearer placeholder"); got != codes.Unimplemented {
		t.Fatalf("got %v", got)
	}
}
func TestFixedDestinationScope(t *testing.T) {
	for _, target := range []string{"external.example:8084", "192.0.2.4:8084", "127.0.0.1:8084", "user@bridge.svc.cluster.local:8084"} {
		if internalAuthority(target, false) {
			t.Errorf("accepted %s", target)
		}
	}
	if !internalAuthority("bridge.system.svc.cluster.local:8084", false) {
		t.Fatal("rejected internal bridge")
	}
	if !internalAuthority("127.0.0.1:18084", true) {
		t.Fatal("rejected explicit outside diagnostic")
	}
	if validURL("http://external.example/path", false) {
		t.Fatal("accepted external target")
	}
}
