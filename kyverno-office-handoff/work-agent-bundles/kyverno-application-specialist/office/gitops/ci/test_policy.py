import fnmatch,json,sys,xml.etree.ElementTree as E
from pathlib import Path
policy=json.loads(Path('deploy/policy.json').read_text())
assert '{{' not in json.dumps(policy), 'Render office placeholders before CI'
rule=policy['spec']['rules'][0]
pattern=rule['validate']['pattern']['spec']['containers'][0]['image']
checks={'valid-image-admitted':fnmatch.fnmatchcase('docker.io/library/busybox:1.36',pattern),'invalid-image-denied':not fnmatch.fnmatchcase('unapproved.example.invalid/library/busybox:1.36',pattern),'enforcement-retained':rule['validate']['failureAction']=='Enforce','scope-retained':policy['kind']=='Policy' and policy['metadata']['namespace']=='{{DEMO_NAMESPACE}}'}
suite=E.Element('testsuite',name='kyverno-policy',tests=str(len(checks)),failures=str(sum(not x for x in checks.values())))
for name,passed in checks.items():
 case=E.SubElement(suite,'testcase',name=name,classname='kyverno-policy')
 if not passed:E.SubElement(case,'failure',message='Policy contract failed')
 print(name, 'PASS' if passed else 'FAIL')
E.ElementTree(suite).write('policy-report.xml',encoding='unicode')
sys.exit(0 if all(checks.values()) else 1)
