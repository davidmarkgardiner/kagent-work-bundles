"""Build from staged approved inputs with no dependency download step."""
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--cli',required=True,type=Path);p.add_argument('--image',required=True);p.add_argument('--engine',default='docker');a=p.parse_args()
root=Path(__file__).resolve().parent;lock=json.loads((root/'versions.lock.json').read_text())
if not a.base.endswith('@'+lock['pythonBaseDigest']):raise ValueError('Unexpected base image digest')
if hashlib.sha256(a.cli.read_bytes()).hexdigest()!=lock['linuxAmd64CLI']['sha256']:raise ValueError('Native CLI checksum mismatch')
subprocess.run([a.engine,'image','inspect',a.base],check=True,stdout=subprocess.DEVNULL)
with tempfile.TemporaryDirectory(prefix='secure-byo-build-') as d:
 stage=Path(d)
 for name in ('runtime','build'):shutil.copytree(root/name,stage/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 shutil.copyfile(a.cli,stage/'kagent');(stage/'kagent').chmod(0o755)
 subprocess.run([a.engine,'build','--network=none','--pull=false','--build-arg','PYTHON_BASE='+a.base,'--build-arg','KAGENT_SHA256='+lock['linuxAmd64CLI']['sha256'],'-f',str(stage/'build/Dockerfile'),'-t',a.image,str(stage)],check=True)
print('Build complete. Publish to the approved internal registry and record its manifest digest before rendering.')
