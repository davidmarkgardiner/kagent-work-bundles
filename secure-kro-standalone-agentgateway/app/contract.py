import hashlib
import json
import os
import re
import unicodedata
import urllib.parse
from pathlib import Path
from typing import NamedTuple

PROFILE = 'docs-readonly-v1'
RUNTIME = 'standalone-kro-v1'
PROOF_SCOPE = ('standalone KRO reference runtime with ConfigMap bindings and synthetic MCP; '
               'not native kagent Agent, Harness, ModelConfig, Skill or Substrate proof')
PACKAGES = ('aks-known-issues', 'kb-aks-bootstrap')
PROOF_FILE = 'references/release-proof.txt'
REQUIRED = (('aks-known-issues', 'references/error-code-map.md'),
            ('kb-aks-bootstrap', 'references/oras-pull-unauthorized.md'),
            ('aks-known-issues', PROOF_FILE), ('kb-aks-bootstrap', PROOF_FILE))
CITATIONS = ('https://learn.microsoft.com/en-us/troubleshoot/azure/azure-kubernetes/error-codes/'
             'vmextensionerror-oraspullunauthorized',)
ANSWER_TERMS = ('AKS-KB-ORAS-212-R1',)
DEMO_TOOL = {'type': 'function', 'function': {
    'name': 'get_demo_status',
    'description': 'Return a labelled synthetic demo status from the platform facade. No Azure or cluster access.',
    'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}}
HOOK_NOTE = ('get_demo_status is also available. Call it exactly once with empty arguments. Its result is '
             'synthetic demo data: include its runProof value verbatim and label it synthetic.')
GOLDEN_SCENARIO = 'golden-docs-readonly-v1'
GOLDEN_PROMPT = (
    'Synthetic documentation case: a node pool in a network-isolated AKS cluster reports '
    'OrasPullUnauthorizedVMExtensionError with vmssCSE exit 212. Load the instructions for BOTH reviewed skills. '
    'Read references/error-code-map.md from aks-known-issues, references/oras-pull-unauthorized.md from '
    'kb-aks-bootstrap and references/release-proof.txt from EACH. Call get_demo_status once. Include both complete '
    'release proof values, the synthetic status runProof, the reviewed evidence code and exact source URLs. '
    'Describe proposed checks and state that no operational investigation or changes were performed.')
EXAMPLE_INSTRUCTIONS = ('Use only the reviewed AKS documentation packages. Explain proposed read-only checks, cite '
                        'exact sources and state that no operational investigation or changes were performed.')


class Limit(NamedTuple):
    minimum: int
    maximum: int
    default: int


LIMITS = {'maxModelCalls': Limit(minimum=2, maximum=8, default=6),
          'maxToolCalls': Limit(minimum=8, maximum=24, default=16),
          'maxMcpCalls': Limit(minimum=1, maximum=1, default=1),
          'maxTokens': Limit(minimum=256, maximum=4096, default=2048),
          'requestTimeoutSeconds': Limit(minimum=5, maximum=120, default=60),
          'deadlineSeconds': Limit(minimum=30, maximum=240, default=180),
          'maxResponseBytes': Limit(minimum=8192, maximum=262144, default=131072)}
MAX_PROMPT = 4000
MAX_INSTRUCTIONS = 2000
MAX_ANSWER_BYTES = 32768
MODEL_SCHEMA = 'standalone-model-binding/v1'
CONTENT_SCHEMA = 'standalone-content-binding/v1'


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def text_ok(value, limit):
    """Bounded single-paragraph text: no control characters at all."""
    return (isinstance(value, str) and 1 <= len(value) <= limit
            and not any(unicodedata.category(c) == 'Cc' for c in value))


def limits_ok(value):
    return (isinstance(value, dict) and set(value) == set(LIMITS)
            and all(type(value[k]) is int and limit.minimum <= value[k] <= limit.maximum
                    for k, limit in LIMITS.items())
            and value['deadlineSeconds'] > value['requestTimeoutSeconds'])


def base_url_ok(value):
    if not isinstance(value, str) or len(value) > 512 or re.search(r'[\s%\x00-\x1f]', value):
        return False
    p = urllib.parse.urlsplit(value)
    return (p.scheme == 'http' and bool(p.hostname) and p.username is None and p.password is None
            and p.path == '' and not p.query and not p.fragment and p.port is not None)


def _read(root, package, path):
    target = Path(root, package, path)
    if '..' in Path(path).parts or Path(path).is_absolute() or target.is_symlink():
        raise ValueError('UnsafeContentPath')
    descriptor = os.open(target, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as handle:
        raw = handle.read(131073)
    if len(raw) > 131072:
        raise ValueError('ContentFileTooLarge')
    return raw


def content_binding(root):
    """Build the immutable content binding from the reviewed recipe and verify every packaged byte."""
    root = Path(root)
    recipe = json.loads(_read(root, '.', 'recipe.json'))
    packages = []
    for name in PACKAGES:
        files = recipe['packages'][name]['files']
        on_disk = {str(p.relative_to(root / name)) for p in (root / name).rglob('*') if p.is_file() or p.is_symlink()}
        if on_disk != set(files) or 'SKILL.md' not in files:
            raise ValueError('PackagedContentMismatch')
        for path, digest in files.items():
            if not re.fullmatch(r'[0-9a-f]{64}', digest) or sha256(_read(root, name, path)) != digest:
                raise ValueError('PackagedContentHashMismatch')
        packages.append({'name': name, 'files': dict(sorted(files.items()))})
    return {'schema': CONTENT_SCHEMA, 'profile': PROFILE, 'packages': packages,
            'required': [list(r) for r in REQUIRED], 'citations': list(CITATIONS), 'answerTerms': list(ANSWER_TERMS)}


def load_packages(binding, root):
    """Return verified package texts only when the mounted binding equals the packaged content."""
    if binding != content_binding(root):
        raise ValueError('ContentBindingMismatch')
    return {p['name']: {path: _read(root, p['name'], path).decode('utf-8') for path in p['files']}
            for p in binding['packages']}


def proofs(texts):
    return [texts[name][PROOF_FILE].strip().split()[-1] for name in PACKAGES]


def resource_result_sha256(skill, path, text):
    """Hash of the vendored loop's load_skill_resource result, for independent verification."""
    return sha256(json.dumps({'skill_name': skill, 'path': path, 'content': text}, sort_keys=True,
                             separators=(',', ':'), ensure_ascii=True).encode())


def arguments_sha256(arguments):
    return sha256(json.dumps(arguments, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode())


def model_binding(model, gateway_base_url, limits):
    return {'schema': MODEL_SCHEMA, 'model': model, 'gatewayBaseURL': gateway_base_url, 'limits': dict(limits)}


def model_binding_ok(value):
    return (isinstance(value, dict) and set(value) == {'schema', 'model', 'gatewayBaseURL', 'limits'}
            and value['schema'] == MODEL_SCHEMA and isinstance(value['model'], str)
            and re.fullmatch(r'[A-Za-z0-9._:/-]{1,128}', value['model']) is not None
            and base_url_ok(value['gatewayBaseURL']) and limits_ok(value['limits']))
