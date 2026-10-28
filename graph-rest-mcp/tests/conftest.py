import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest

from app.seed import seed


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.fixture(scope="session")
def database(tmp_path_factory):
    database = tmp_path_factory.mktemp("fixture") / "graph.duckdb"
    seed(database, ROOT / "data/fixture.json")
    return database


@pytest.fixture(scope="session")
def servers(database):
    rest_port, mcp_port = free_port(), free_port()
    environment = {**os.environ, "GRAPH_DB_PATH": str(database), "GRAPH_REST_URL": f"http://127.0.0.1:{rest_port}/get-context", "GRAPH_SERVICE_MODE": "local", "PYTHONDONTWRITEBYTECODE": "1"}
    environment.pop("GRAPH_AUTH_TOKEN_FILE", None)
    commands = [
        [sys.executable, "-m", "uvicorn", "app.rest:app", "--host", "127.0.0.1", "--port", str(rest_port), "--no-access-log", "--log-level", "critical"],
        [sys.executable, "-c", f"from app.mcp_server import mcp; mcp.run(transport='streamable-http',host='127.0.0.1',port={mcp_port},path='/mcp',stateless_http=True,json_response=True,show_banner=False,log_level='CRITICAL',uvicorn_config={{'access_log':False}})"],
    ]
    processes = [subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for command in commands]
    try:
        for port, process in zip((rest_port, mcp_port), processes):
            for _ in range(100):
                if process.poll() is not None:
                    pytest.fail("test server exited before readiness")
                try:
                    if httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=0.2).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail("test server readiness timed out")
        yield {"rest": f"http://127.0.0.1:{rest_port}", "mcp": f"http://127.0.0.1:{mcp_port}/mcp"}
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
