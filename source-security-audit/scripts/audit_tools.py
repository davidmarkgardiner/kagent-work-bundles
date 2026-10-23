#!/usr/bin/env python3
"""Local input and output gates; these do not run an audit or prove findings true."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys

BUNDLE = Path(__file__).resolve().parents[1]
LOCK_DIGEST = 'bdc24192649e6738e95a50a0d350769ef09d4e4c896171e272a3b902d17d4322'
COMMIT = 'c1c8a8c1471069fb0e188eeaff69b8e8db6564a8'
MAX_BYTES = 5 * 1024 * 1024
ROLES = {'recon', 'hunter', 'candidate_verifier', 'coverage_critic', 'final_verifier', 'final_critic'}
ARTIFACTS = ('run-metadata.json', 'architecture.md', 'coverage-ledger.json', 'findings.json',
             'REPORT.md', 'FINDINGS-DETAIL.md', 'NEEDS-VALIDATION.md')


class GateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def absolute_path(value):
    require(isinstance(value, str) and value.startswith('/') and '\x00' not in value,
            'expected absolute path')
    path = Path(value)
    require('..' not in path.parts, 'path traversal forbidden')
    current = Path('/')
    for part in path.parts[1:]:
        current /= part
        require(not current.is_symlink(), 'symlink path components forbidden')
        if current.exists() and current != path:
            require(current.is_dir(), 'path ancestor is not a directory')
    return path


def relative_path(value):
    require(isinstance(value, str) and value and '\\' not in value and
            all(ord(c) >= 32 for c in value), 'invalid relative path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(p not in ('', '.', '..', '.git')
            for p in value.split('/')), 'unsafe relative path')
    return path


def read_file(path, nonempty=False):
    path = absolute_path(str(path))
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_BYTES, 'expected bounded regular file')
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES and (data or not nonempty), 'empty or oversized file')
    return data


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(read_file(path), object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON number')))


def verify_upstream(bundle=BUNDLE):
    lock = read_json(bundle / 'UPSTREAM.lock.json')
    digest = hashlib.sha256(json.dumps(lock, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(digest == LOCK_DIGEST and lock['commit'] == COMMIT and
            lock['repository'] == 'https://github.com/cloudflare/security-audit-skill',
            'upstream lock differs from trusted pinned identity')
    expected = lock['files_sha256']
    require(len(expected) == 21, 'expected 21 upstream assets')
    root = absolute_path(str(bundle / 'upstream'))
    require(root.is_dir(), 'upstream directory missing')
    actual = set()
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            require(not (Path(parent) / name).is_symlink(), 'upstream directory symlink forbidden')
        for name in files:
            path = Path(parent) / name
            rel = path.relative_to(root).as_posix()
            require(rel in expected, 'unexpected upstream asset')
            require(hashlib.sha256(read_file(path)).hexdigest() == expected[rel], 'upstream asset hash mismatch')
            actual.add(rel)
    require(actual == set(expected), 'missing upstream assets')
    require({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_dir()} == {'security-audit'},
            'unexpected upstream directories')


def model_policy(value):
    require(isinstance(value, dict) and set(value) == {'hunter', 'verifier', 'require_different_models'},
            'invalid model_policy fields')
    for field in ('hunter', 'verifier'):
        require(isinstance(value[field], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+ -]*', value[field]),
                'concrete model name required')
    require(type(value['require_different_models']) is bool, 'model diversity flag must be boolean')
    require(not value['require_different_models'] or value['hunter'] != value['verifier'],
            'model policy requires different hunter and verifier models')


def profile_budget(profile, budget):
    require(profile in ('quick', 'standard', 'deep'), 'invalid profile')
    require(budget is None or (type(budget) is int and budget >= (7 if profile == 'quick' else 8)),
            'budget cannot fund reconnaissance and reserves (quick >=7; standard/deep >=8)')


def git_read(target, *args):
    require(args in {('rev-parse', '--show-toplevel'), ('rev-parse', '--verify', 'HEAD'),
                     ('ls-tree', '-rz', '--full-tree', 'HEAD'),
                     ('ls-files', '--stage', '-z', '--no-recurse-submodules'),
                     ('ls-files', '--others', '--exclude-standard', '-z', '--no-recurse-submodules')},
            'unsupported git metadata query')
    git = shutil.which('git', path=os.defpath)
    require(git is not None, 'trusted git executable unavailable')
    env = {'PATH': os.defpath, 'HOME': '/nonexistent', 'LANG': 'C', 'LC_ALL': 'C',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
           'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_LAZY_FETCH': '1',
           'GIT_NO_REPLACE_OBJECTS': '1'}
    result = subprocess.run([git, '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
                             '-c', 'core.untrackedCache=false', '-C', str(target), *args],
                            env=env, capture_output=True, timeout=30)
    require(result.returncode == 0, 'read-only git inspection failed')
    require(len(result.stdout) <= MAX_BYTES, 'git metadata exceeds limit')
    return result.stdout.decode('utf-8').strip()


def dirty_snapshot(target, source_ref):
    """Compare raw Git metadata and blob bytes; never invoke status or clean filters."""
    head, index = {}, {}
    for row in git_read(target, 'ls-tree', '-rz', '--full-tree', 'HEAD').split('\x00'):
        if row:
            fields, name = row.split('\t', 1)
            mode, kind, oid = fields.split(' ')
            head[name] = (mode, oid)
    for row in git_read(target, 'ls-files', '--stage', '-z', '--no-recurse-submodules').split('\x00'):
        if row:
            fields, name = row.split('\t', 1)
            mode, oid, stage = fields.split(' ')
            if stage != '0' or name in index:
                return True
            index[name] = (mode, oid)
    if head != index or git_read(target, 'ls-files', '--others', '--exclude-standard', '-z', '--no-recurse-submodules'):
        return True
    for name, (mode, oid) in index.items():
        if mode not in ('100644', '100755'):
            return True  # Symlinks and submodules need an independently pinned snapshot.
        try:
            path = target / relative_path(name)
            data = read_file(path)
            if bool(path.stat().st_mode & 0o111) != (mode == '100755'):
                return True
            blob = b'blob ' + str(len(data)).encode() + b'\x00' + data
            if hashlib.new('sha1' if len(source_ref) == 40 else 'sha256', blob).hexdigest() != oid:
                return True
        except (ValueError, OSError):
            return True
    return False


def preflight(request, bundle=BUNDLE, output_must_be_new=True):
    fields = {'target', 'source_ref', 'output_dir', 'profile', 'scope_paths', 'execution_mode',
              'model_policy', 'agent_budget', 'prior_runs', 'scanner_reports'}
    require(isinstance(request, dict) and fields <= set(request) and set(request) <= fields | {'require_clean'},
            'request missing required or contains unknown fields')
    require(request['execution_mode'] == 'source-only', 'only source-only execution is supported')
    model_policy(request['model_policy'])
    profile_budget(request['profile'], request['agent_budget'])
    target, output = absolute_path(request['target']), absolute_path(request['output_dir'])
    require(target.is_dir() and (not output.exists() if output_must_be_new else output.is_dir()),
            'target must exist; output must be NEW for preflight or an existing run for validation')
    for root in (target, bundle.resolve()):
        require(not output.is_relative_to(root) and not root.is_relative_to(output),
                'output must be outside and must not contain target or bundle')
    require(output.parent.is_dir(), 'output parent must exist')
    require(git_read(target, 'rev-parse', '--show-toplevel') == str(target), 'target must be git root')
    require(isinstance(request['source_ref'], str) and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', request['source_ref']),
            'source_ref must be a full commit hash')
    require(git_read(target, 'rev-parse', '--verify', 'HEAD') == request['source_ref'], 'source_ref differs from HEAD')
    scopes = request['scope_paths']
    require(isinstance(scopes, list) and scopes and len(scopes) == len(set(scopes)), 'unique nonempty scope_paths required')
    for value in scopes:
        path = target / relative_path(value)
        absolute_path(str(path))
        require(path.exists() and (path.is_file() or path.is_dir()), 'scope path missing or nonregular')
    for field in ('prior_runs', 'scanner_reports'):
        require(isinstance(request[field], list), f'{field} must be a list')
    for value in request['prior_runs']:
        require(absolute_path(value).is_dir(), 'prior run directory missing')
    for report in request['scanner_reports']:
        require(isinstance(report, dict) and {'tool', 'path', 'source_ref'} <= set(report) and
                set(report) <= {'tool', 'path', 'source_ref', 'version', 'created_at'}, 'invalid scanner report metadata')
        require(all(isinstance(v, str) and v.strip() for v in report.values()), 'scanner metadata must be text')
        require(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', report['source_ref']), 'invalid scanner source_ref')
        read_file(absolute_path(report['path']))
    dirty = dirty_snapshot(target, request['source_ref'])
    require(type(request.get('require_clean', True)) is bool, 'require_clean must be boolean')
    require(not dirty or not request.get('require_clean', True), 'dirty target; request require_clean=false to acknowledge')
    return {'status': 'PREFLIGHT_ONLY', 'target': str(target), 'output_dir': str(output),
            'source_ref': request['source_ref'], 'profile': request['profile'], 'dirty': dirty,
            'source_ref_covers_worktree': not dirty, 'execution_mode': 'source-only',
            'target_code_executed': False, 'audit_started': False}


def node_validator(bundle, script, path):
    node = shutil.which('node')
    require(node is not None, 'Node.js required')
    result = subprocess.run([node, str(bundle / 'upstream/security-audit' / script), str(path)],
                            capture_output=True, timeout=30,
                            env={'PATH': os.defpath, 'HOME': '/nonexistent', 'LANG': 'C'})
    # Validator diagnostics may include source/secret snippets supplied in hostile inputs.
    require(result.returncode == 0, f'actual upstream {script} rejected input; inspect privately')


def verify_checksums(bundle=BUNDLE):
    expected = {}
    for line in read_file(bundle / 'CHECKSUMS.sha256', nonempty=True).decode('utf-8').splitlines():
        require(re.fullmatch(r'[0-9a-f]{64}  .+', line), 'malformed checksum entry')
        digest, value = line.split('  ', 1)
        relative_path(value)
        require(value not in expected and value != 'CHECKSUMS.sha256', 'duplicate or self checksum')
        expected[value] = digest
    actual = set()
    for parent, dirs, files in os.walk(bundle, followlinks=False):
        require(all(not (Path(parent) / d).is_symlink() for d in dirs), 'bundle directory symlink forbidden')
        for name in files:
            path = Path(parent) / name
            rel = path.relative_to(bundle).as_posix()
            if rel == 'CHECKSUMS.sha256':
                continue
            require(rel in expected, 'unexpected bundle asset')
            require(hashlib.sha256(read_file(path)).hexdigest() == expected[rel], 'bundle hash mismatch')
            actual.add(rel)
    require(actual == set(expected), 'bundle assets missing')


def verify_manifest(bundle=BUNDLE):
    path = bundle / 'manifests/agent.yaml'
    import yaml
    docs = list(yaml.safe_load_all(read_file(path)))
    require(len(docs) == 1 and isinstance(docs[0], dict), 'expected one reviewer manifest')
    doc = docs[0]
    require(doc.get('apiVersion') == 'kagent.dev/v1alpha2' and doc.get('kind') == 'Agent', 'invalid reviewer kind')
    spec = doc.get('spec', {})
    require(set(spec) <= {'description', 'type', 'declarative'} and spec.get('type') == 'Declarative',
            'reviewer cannot add runtime capabilities')
    declarative = spec.get('declarative', {})
    require(set(declarative) <= {'modelConfig', 'systemMessage', 'tools', 'runtime', 'a2aConfig'} and
            declarative.get('tools') == [] and declarative.get('runtime', 'python') == 'python',
            'reviewer must have explicit empty tools and no skills or runtime extras')
    a2a = declarative.get('a2aConfig', {})
    require(isinstance(a2a, dict) and set(a2a) <= {'skills'}, 'a2aConfig allows metadata skills only')
    skills = a2a.get('skills', [])
    require(isinstance(skills, list), 'a2a metadata skills must be array')
    for skill in skills:
        require(isinstance(skill, dict) and set(skill) <= {'id', 'name', 'description', 'inputModes', 'outputModes',
                'tags', 'examples'} and {'id', 'name', 'description'} <= set(skill), 'invalid A2A metadata fields')
        require(all(isinstance(skill[k], str) and skill[k].strip() for k in ('id', 'name', 'description')),
                'A2A descriptive fields must be text')
        for key in ('inputModes', 'outputModes', 'tags', 'examples'):
            require(key not in skill or (isinstance(skill[key], list) and
                    all(isinstance(x, str) and x.strip() for x in skill[key])), 'invalid A2A metadata list')
        require(all(skill.get(key, ['text']) == ['text'] for key in ('inputModes', 'outputModes')),
                'reviewer modes must be text only')
    require(isinstance(declarative.get('modelConfig'), str) and declarative['modelConfig'].strip() and
            isinstance(declarative.get('systemMessage'), str) and declarative['systemMessage'].strip(),
            'reviewer model and instructions required')
    labels = doc.get('metadata', {}).get('labels', {})
    require(labels.get('platform.com/evidence-only') == 'true' and labels.get('platform.com/type') == 'triage',
            'reviewer safety labels required')
    overlay = bundle / 'manifests/kustomization.yaml'
    if overlay.exists():
        require(yaml.safe_load(read_file(overlay)) == {'apiVersion': 'kustomize.config.k8s.io/v1beta1',
                'kind': 'Kustomization', 'resources': ['agent.yaml']}, 'reviewer overlay must contain only agent.yaml')


def validate_run(request, run, bundle=BUNDLE):
    verify_upstream(bundle)
    snapshot = preflight(request, bundle, output_must_be_new=False)
    run = absolute_path(str(run))
    require(run.is_dir(), 'run directory missing')
    require(str(run) == request['output_dir'], 'run differs from requested output_dir')
    require(not run.is_relative_to(bundle.resolve()), 'private run must be outside bundle')
    for name in ARTIFACTS:
        read_file(run / name, nonempty=True)
    metadata = read_json(run / 'run-metadata.json')
    require(isinstance(metadata, dict), 'run metadata must be object')
    require(metadata.get('execution_policy') == 'sandboxed-source-and-local-only',
            'run execution_policy must match pinned upstream source/local boundary')
    for key in ('target', 'output_dir', 'source_ref', 'profile', 'scope_paths', 'execution_mode', 'model_policy'):
        require(metadata.get(key) == request[key], 'run metadata differs from explicit request: ' + key)
    require(metadata.get('execution_mode') == 'source-only', 'only source-only run validation supported')
    require(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', str(metadata.get('source_ref', ''))), 'invalid run source_ref')
    policy = metadata.get('model_policy')
    model_policy(policy)
    budget = metadata.get('budget', metadata.get('agent_budget'))
    require(budget == request['agent_budget'], 'run budget differs from explicit request')
    require('budget' in metadata or 'agent_budget' in metadata, 'run budget required (null allowed)')
    require('agent_budget' not in metadata or metadata['agent_budget'] == budget, 'budget aliases disagree')
    profile = metadata.get('profile')
    profile_budget(profile, budget)
    require(metadata.get('run_status') in ('complete', 'incomplete'), 'run must be complete or incomplete')
    if metadata['run_status'] == 'incomplete':
        require(isinstance(metadata.get('incomplete_reason'), str) and metadata['incomplete_reason'].strip(),
                'incomplete run requires reason')
    for script, name in (('validate-findings.cjs', 'findings.json'),
                         ('validate-coverage-ledger.cjs', 'coverage-ledger.json')):
        node_validator(bundle, script, run / name)
    findings, ledger = read_json(run / 'findings.json'), read_json(run / 'coverage-ledger.json')
    if profile == 'quick':
        require(all(unit['wave'] == 1 and not unit['attempts'] and
                    unit['canonical_refs']['subsystem'] == 'profile/quick/all-in-scope-subsystems'
                    for unit in ledger), 'quick ledger must use one wave and fixed canonical subsystem')
    require(all(f['verdict'] != 'confirmed' for f in findings), 'source-only run cannot contain confirmed findings')
    require(all(check['method'] == 'source' for unit in ledger
                for attempt in [unit, *unit.get('attempts', [])] for check in attempt['local_checks']),
            'source-only ledger cannot claim executed local checks')
    receipts = read_json(run / 'delegation-receipts.json')
    require(isinstance(receipts, list) and len(receipts) <= 1000, 'receipts must be bounded array')
    require(budget is None or len(receipts) <= budget, 'receipt count exceeds invocation budget')
    ids, contexts, receipt_paths = set(), set(), set()
    for record in receipts:
        require(isinstance(record, dict) and set(record) == {'agent_id', 'role', 'model', 'context_id',
                'status', 'receipt_path', 'fingerprints'}, 'invalid delegation receipt fields')
        require(record['role'] in ROLES and record['status'] in ('completed', 'failed', 'incomplete'),
                'invalid receipt role/status')
        require(isinstance(record['agent_id'], str) and re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', record['agent_id'])
                and not re.fullmatch(r'con|prn|aux|nul|com[1-9]|lpt[1-9]', record['agent_id']),
                'receipt agent_id must use upstream canonical lowercase safe identifier')
        for field, seen in (('agent_id', ids), ('context_id', contexts), ('receipt_path', receipt_paths)):
            value = record[field]
            require(isinstance(value, str) and value.strip() and value not in seen, 'receipt identifiers must be unique')
            seen.add(value)
        require(isinstance(record['model'], str) and record['model'].strip(), 'receipt model required')
        path = run / relative_path(record['receipt_path'])
        require(path.name not in ARTIFACTS and path.name != 'delegation-receipts.json', 'receipt cannot be shared artifact')
        read_file(path, nonempty=True)
        require(isinstance(record['fingerprints'], list) and all(isinstance(f, str) and f for f in record['fingerprints'])
                and len(record['fingerprints']) == len(set(record['fingerprints'])), 'invalid receipt fingerprints')
        if record['role'] == 'hunter':
            require(record['model'] == policy['hunter'], 'hunter model differs from policy')
        if record['role'] in ('candidate_verifier', 'final_verifier'):
            require(record['model'] == policy['verifier'], 'verifier model differs from policy')
            require(len(record['fingerprints']) == 1, 'each verifier must own exactly one candidate')
    def completed(role):
        return [r for r in receipts if r['role'] == role and r['status'] == 'completed']
    known_fingerprints = {finding['fingerprint'] for finding in findings}
    ledger_fingerprints = {fingerprint for unit in ledger for attempt in [unit, *unit.get('attempts', [])]
                           for fingerprint in attempt['result_fingerprints']}
    require(known_fingerprints <= ledger_fingerprints, 'final record has no ledger candidate')
    require(all(set(r['fingerprints']) <= ledger_fingerprints for r in receipts), 'receipt references unknown candidate')
    completed_ids = {r['agent_id'] for r in receipts if r['status'] == 'completed'}
    completed_roles = {r['agent_id']: r['role'] for r in receipts if r['status'] == 'completed'}
    gaps = []
    if snapshot['dirty']:
        gaps.append('dirty snapshot is not pinned by source_ref')
    if len(completed('recon')) < 4 or not completed('hunter'):
        gaps.append('missing baseline reconnaissance or hunter receipts')
    if len(completed('coverage_critic')) < 1:
        gaps.append('missing coverage critic')
    if profile == 'quick':
        require(len([r for r in receipts if r['role'] == 'coverage_critic']) <= 1, 'quick allows exactly one coverage critic')
    elif not completed('final_critic'):
        gaps.append('missing distinct final critic')
    if not ledger or any(u['status'] in ('planned', 'in_progress', 'blocked') for u in ledger):
        gaps.append('coverage ledger has unassessed work')
    if ledger_fingerprints != known_fingerprints:
        gaps.append('candidate ledger and final dispositions disagree')
    if any(check['agent_id'] not in completed_ids for unit in ledger
           for attempt in [unit, *unit.get('attempts', [])] for check in attempt['local_checks']):
        gaps.append('coverage evidence has no completed delegation receipt')
    for unit in ledger:
        for attempt in [unit, *unit.get('attempts', [])]:
            if attempt['status'] in ('covered', 'candidate', 'blocked') and completed_roles.get(attempt['agent_id']) != 'hunter':
                gaps.append('coverage assignment lacks completed hunter ownership')
            if any(completed_roles.get(check['agent_id']) not in ('hunter', 'candidate_verifier', 'final_verifier')
                   for check in attempt['local_checks']):
                gaps.append('coverage checks lack hunter or verifier ownership')
    for finding in findings:
        fingerprint = finding['fingerprint']
        hunters = [r for r in completed('hunter') if fingerprint in r['fingerprints']]
        verifiers = [r for r in completed('candidate_verifier') if fingerprint in r['fingerprints']]
        if not hunters or not verifiers:
            gaps.append('candidate missing hunter or fresh verifier')
        if profile != 'quick' and not any(fingerprint in r['fingerprints'] for r in completed('final_verifier')):
            gaps.append('candidate missing distinct final verifier')
        if policy['require_different_models'] and hunters and verifiers:
            require(all(h['model'] != v['model'] for h in hunters for v in verifiers), 'candidate models not diverse')
    if any(r['status'] != 'completed' for r in receipts):
        gaps.append('delegated invocation incomplete or failed')
    require(not gaps or metadata['run_status'] == 'incomplete', 'complete claim contradicts delegation or coverage gaps')
    return (2 if metadata['run_status'] == 'incomplete' else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify-upstream', 'request-preflight', 'validate-run', 'verify-checksums', 'verify-manifest'))
    parser.add_argument('path', nargs='?')
    parser.add_argument('run', nargs='?')
    args = parser.parse_args()
    try:
        if args.action in ('verify-upstream', 'verify-checksums', 'verify-manifest'):
            require(args.path is None and args.run is None, 'integrity command accepts no path')
            {'verify-upstream': verify_upstream, 'verify-checksums': verify_checksums,
             'verify-manifest': verify_manifest}[args.action]()
            print('PASS: ' + args.action)
            return 0
        require(args.path is not None, 'input path required')
        if args.action == 'request-preflight':
            require(args.run is None, 'preflight accepts one request path')
            print(json.dumps(preflight(read_json(Path(args.path).absolute())), indent=2))
            return 0
        require(args.run is not None, 'validate-run requires REQUEST RUN')
        code = validate_run(read_json(Path(args.path).absolute()), Path(args.run).absolute())
        print(('INCOMPLETE' if code == 2 else 'VALID') + ': artifact shape and receipt references only; no vulnerability truth or receipt authenticity proven')
        return code
    except GateError as error:
        print('INVALID: ' + str(error), file=sys.stderr)
        return 1
    except (ValueError, OSError, KeyError, TypeError, ImportError, subprocess.SubprocessError, RecursionError):
        print('INVALID: input, integrity, policy, or artifact gate failed; no audit executed', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
