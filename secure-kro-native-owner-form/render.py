"""Render the reviewed native KRO profile without contacting Kubernetes."""
import argparse
import json
from pathlib import Path

import owner_schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    outputs = {
        'resourcegraphdefinition.json': owner_schema.rgd(profile),
        'owner-policy.json': owner_schema.admission_policy(profile),
        'owner-binding.json': owner_schema.admission_binding(),
        'secure-agent.json': owner_schema.owner_example(profile),
        'owner-spec.schema.json': owner_schema.owner_spec_schema(profile),
    }
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, value in outputs.items():
        path = args.output / name
        path.write_text(json.dumps(value, indent=2) + '\n')
        path.chmod(0o600)
    print(json.dumps({'result': 'Rendered', 'files': sorted(outputs)}))


if __name__ == '__main__':
    main()
