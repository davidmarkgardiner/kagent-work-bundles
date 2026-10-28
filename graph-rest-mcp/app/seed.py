import argparse
import json
from pathlib import Path

import duckdb


def seed(database: Path, fixture: Path) -> None:
    data = json.loads(fixture.read_text())
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database)) as connection:
        connection.execute("CREATE TABLE nodes (environment VARCHAR, priority INTEGER, category VARCHAR, payload VARCHAR)")
        connection.execute("CREATE TABLE edges (environment VARCHAR, payload VARCHAR)")
        connection.executemany(
            "INSERT INTO nodes VALUES (?, ?, ?, ?)",
            [(node["environment"], index, node["category"], json.dumps(node["value"])) for index, node in enumerate(data["nodes"])],
        )
        connection.executemany("INSERT INTO edges VALUES (?, ?)", [(edge["environment"], json.dumps(edge["value"])) for edge in data["edges"]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=Path("data/fixture.json"))
    args = parser.parse_args()
    seed(args.database, args.fixture)
