#!/usr/bin/env python3
"""Create an allowlisted source handoff without lab keys, credentials, or bridges."""
import argparse
import hashlib
from pathlib import Path
import stat
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.output.exists():
        parser.error("Output already exists; choose a new path")
    names = ["FRONT-SHEET.md", "DEMO-SCENARIOS.md", "ENTRA-ISOLATION-DEMO.md", "WORK-BUNDLE-README.md", "WORK-AGENT-PROMPT.md", "AKS-ISTIO.md",
             "PLATFORM-PREREQUISITES.md", "IMAGE-IMPORT.md", "LIVE-INTEGRATION.md", "LIVE-HOMELAB.md", "ROLLBACK.md", "Dockerfile", ".dockerignore", ".gitignore",
             "requirements-ops.txt", "image-lock.json", "backend.py", "telemetry.py", "substrate_call.py",
             "workflow_demo.py", "live_gitlab.py", "test_live_gitlab.py", "isolation_demo.py", "test_isolation_demo.py", "test_telemetry.py", "test_substrate_call.py", "test_workflow_demo.py", "test_verify_https.py"]
    files = [root / name for name in names]
    for directory in ["ui", "deploy", "scripts"]:
        files.extend(p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    files.extend(p for p in (root / "evidence").glob("portable-*.json"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    hashes = []
    with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED) as archive:
        def write(relative, data):
            entry = zipfile.ZipInfo("otel-agent-flow/" + relative)
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)

        for path in sorted(set(files)):
            if path.is_symlink():
                raise SystemExit("Refuse symlink in source package")
            relative = path.relative_to(root).as_posix()
            data = path.read_bytes()
            write(relative, data)
            hashes.append(hashlib.sha256(data).hexdigest() + "  " + relative)
        readme = (root / "WORK-BUNDLE-README.md").read_bytes()
        write("README.md", readme)
        hashes.append(hashlib.sha256(readme).hexdigest() + "  README.md")
        write("SHA256SUMS", ("\n".join(hashes) + "\n").encode())
    checksum = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(checksum + "  " + args.output.name + "\n")
    print(str(args.output))
    print("SHA-256 " + checksum)


if __name__ == "__main__":
    main()
