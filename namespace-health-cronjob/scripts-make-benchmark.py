"""Render 20 sequential report-only assessments using the exact assessor image."""
import subprocess,sys
from pathlib import Path
import yaml
root=Path(__file__).resolve().parent
raw=subprocess.check_output([sys.executable,str(root/'scripts-make-canary.py'),sys.argv[1] if len(sys.argv)>1 else '/tmp/namespace-health-lab.yaml','report-only'],text=True)
job=yaml.safe_load(raw)
job['metadata']['generateName']='namespace-health-benchmark-'
container=job['spec']['template']['spec']['containers'][0]
container['command']=['python','-c']
container['args']=['import json,resource\nfrom publish import run\nfor i in range(20): run()\nr=resource.getrusage(resource.RUSAGE_SELF)\nprint(json.dumps({"benchmark_summary":{"runs":20,"cpu_user_seconds":r.ru_utime,"cpu_system_seconds":r.ru_stime,"maxrss_kib":r.ru_maxrss}}))']
print(yaml.safe_dump(job,sort_keys=False))
