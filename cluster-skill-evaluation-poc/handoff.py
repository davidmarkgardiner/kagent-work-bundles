#!/usr/bin/env python3
"""Generate local GitLab MR prose from an independently recomputed passing receipt."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text())
    if receipt['phase'] != 'Passed' or not receipt.get('sourceCommit') or not receipt.get('evidenceRef'):
        parser.error('a passing controller receipt with provenance is required')
    text = ('# Skill evaluation handoff\n\nVerdict: Passed (native tool and configured term checks).\n\n'
            f"Skill content SHA256: `{receipt['skillContentSha256']}`\n\nSource commit: `{receipt['sourceCommit']}`\n\n"
            f"Evidence ConfigMap: `{receipt['evidenceRef']}`\n\nEvidence SHA256: `{receipt['evidenceSha256']}`\n\n"
            'Semantic score: not_scored. DeepEval: not_used.\n\n'
            'This is local draft prose. No GitLab API call, MR creation, token, or live publication occurred.\n')
    with args.output.open('x') as stream:
        stream.write(text)


if __name__ == '__main__':
    main()
