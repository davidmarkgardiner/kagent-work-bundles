"""Emit five isolated zero-available critical workload fixtures."""
import sys
from pathlib import Path
import yaml
source=yaml.safe_load((Path(__file__).resolve().parent/'manifests/lab-critical-fixture.yaml').read_text())
for suffix in 'abcde':
    item=dict(source)
    item['metadata']=dict(source['metadata'],namespace=f'health-fixture-{suffix}')
    yaml.safe_dump(item,sys.stdout,sort_keys=False)
    sys.stdout.write('---\n')
