#!/usr/bin/env python3
"""Approved Python helper with immutable code: agent | facade | golden | selftest."""
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def selftest(root=HERE / 'content'):
    for name in ('agent', 'authority', 'facade', 'golden'):
        importlib.import_module(name)
    import common
    import contract
    binding = contract.content_binding(root)
    texts = contract.load_packages(binding, root)
    print(json.dumps({'event': 'selftest', 'profile': contract.PROFILE, 'contentSha256': common.canonical(binding),
                      'packages': sorted(texts), 'proofs': len(contract.proofs(texts))}), flush=True)
    return 0


def main(argv):
    mode, rest = (argv[0], argv[1:]) if argv else ('', [])
    if mode == 'agent':
        import agent
        return agent.main(rest)
    if mode == 'facade':
        import facade
        return facade.main(rest)
    if mode == 'golden':
        import golden
        return golden.main(rest)
    if mode == 'selftest' and not rest:
        return selftest()
    print('usage: main.py agent|facade|golden --request NAME|selftest', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
