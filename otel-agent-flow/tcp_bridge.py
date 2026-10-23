"""Forward a lab bridge socket to an existing loopback-only SSH tunnel."""
import argparse
import select
import socket
import socketserver


class Relay(socketserver.BaseRequestHandler):
    def handle(self):
        with socket.create_connection(("127.0.0.1", self.server.target_port), timeout=10) as upstream:
            peers = {self.request: upstream, upstream: self.request}
            while True:
                ready, _, _ = select.select(list(peers), [], [], 120)
                if not ready:
                    return
                for source in ready:
                    data = source.recv(65536)
                    if not data:
                        return
                    peers[source].sendall(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", required=True)
    parser.add_argument("--listen", type=int, required=True)
    parser.add_argument("--target", type=int, required=True)
    args = parser.parse_args()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((args.bind, args.listen), Relay) as server:
        server.daemon_threads = True
        server.target_port = args.target
        server.serve_forever()
