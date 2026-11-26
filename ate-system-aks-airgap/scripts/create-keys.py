#!/usr/bin/env python3
"""Creates the signing pools and API authentication config no chart creates.

Mirrors go/core/pkg/install/substrate_init.go in kagent v1.0.1. Existing objects are
never overwritten. CA certificates are valid for ONE YEAR and nothing renews them.
Private keys exist only in a private temporary directory and in the Secrets.
Usage: create-keys.py <kube-context>
"""
import base64, json, os, secrets, subprocess, sys, tempfile

CTX = sys.argv[1]
b64 = lambda b: base64.b64encode(b).decode()
url = lambda b: base64.urlsafe_b64encode(b).decode().rstrip('=')


def run(*cmd, data=None):
    return subprocess.run(cmd, input=data, capture_output=True, check=True).stdout


def kubectl(*args, data=None):
    return run('kubectl', '--context', CTX, *args, data=data)


def exists(kind, ns, name):
    return subprocess.run(['kubectl', '--context', CTX, '-n', ns, 'get', kind, name], capture_output=True).returncode == 0


def create(obj):
    kubectl('create', '-f', '-', data=json.dumps(obj).encode())
    print('created', obj['kind'], obj['metadata']['namespace'] + '/' + obj['metadata']['name'])


def secret(ns, name, data, kind='Opaque'):
    create({'apiVersion': 'v1', 'kind': 'Secret', 'type': kind, 'metadata': {'name': name, 'namespace': ns},
            'data': {k: b64(v) for k, v in data.items()}})


def new_key(path, algorithm):
    args = ['-algorithm', 'ED25519'] if algorithm == 'ed25519' else ['-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-256']
    run('openssl', 'genpkey', *args, '-out', path)
    # PKCS#8 explicitly: `openssl pkey -outform DER` writes SEC1 for EC keys, which Substrate rejects.
    return run('openssl', 'pkcs8', '-topk8', '-nocrypt', '-in', path, '-outform', 'DER')


def ca_pool(tmp, ns, name, algorithm):
    if exists('secret', ns, name):
        return print('kept', ns + '/' + name)
    key, crt, cfg = (os.path.join(tmp, name + s) for s in ('.key', '.crt', '.cnf'))
    der_key = new_key(key, algorithm)
    with open(cfg, 'w') as f:
        f.write('[req]\ndistinguished_name=dn\nprompt=no\nx509_extensions=ca\n[dn]\nCN=%s\n'
                '[ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,digitalSignature,keyCertSign\n'
                'subjectKeyIdentifier=hash\n' % secrets.token_hex(13))
    run('openssl', 'req', '-new', '-x509', '-key', key, '-days', '365', '-config', cfg, '-out', crt)
    der_crt = run('openssl', 'x509', '-in', crt, '-outform', 'DER')
    pool = {'CAs': [{'ID': '1', 'SigningKeyPKCS8': b64(der_key), 'RootCertificateDER': b64(der_crt)}], 'ActiveForSigning': '1'}
    secret(ns, name, {'pool': json.dumps(pool).encode(), 'tls.crt': open(crt, 'rb').read(), 'tls.key': open(key, 'rb').read()},
           'kubernetes.io/tls')


def jwt_pool(tmp, ns, name):
    if exists('secret', ns, name):
        return print('kept', ns + '/' + name)
    key = os.path.join(tmp, name + '.key')
    der_key = new_key(key, 'ec')
    point = run('openssl', 'pkey', '-in', key, '-pubout', '-outform', 'DER')[-65:]
    assert point[0] == 4, 'expected an uncompressed P-256 point'
    pool = {'Authorities': [{'ID': '1', 'Algorithm': 'ES256', 'SigningKeyPKCS8': b64(der_key)}], 'ActiveForSigning': '1'}
    jwks = {'keys': [{'kty': 'EC', 'crv': 'P-256', 'x': url(point[1:33]), 'y': url(point[33:]), 'kid': '1', 'alg': 'ES256', 'use': 'sig'}]}
    secret(ns, name, {'pool': json.dumps(pool).encode(), 'jwks': json.dumps(jwks).encode()})


def main():
    system, podcert = 'ate-system', 'podcertificate-controller-system'
    with tempfile.TemporaryDirectory() as tmp:
        jwt_pool(tmp, system, 'actor-id-jwt-pool')
        ca_pool(tmp, system, 'actor-id-ca-pool', 'ed25519')
        if not exists('secret', system, 'actor-id-ca-certs'):
            raw = json.loads(kubectl('-n', system, 'get', 'secret', 'actor-id-ca-pool', '-o', 'json'))
            pool = json.loads(base64.b64decode(raw['data']['pool']))
            pem = ''.join('-----BEGIN CERTIFICATE-----\n%s\n-----END CERTIFICATE-----\n' % '\n'.join(
                c['RootCertificateDER'][i:i + 64] for i in range(0, len(c['RootCertificateDER']), 64)) for c in pool['CAs'])
            secret(system, 'actor-id-ca-certs', {'ca.crt': pem.encode()})
        ca_pool(tmp, system, 'egress-mitm-ca-pool', 'ec')
        for name in ('service-dns-ca-pool', 'pod-identity-ca-pool', 'postgres-ca-pool'):
            ca_pool(tmp, podcert, name, 'ed25519')
    if not exists('configmap', system, 'ate-api-authentication'):
        in_cluster = 'https://kubernetes.default.svc'
        issuer = json.loads(kubectl('get', '--raw', '/.well-known/openid-configuration')).get('issuer') or in_cluster
        text = 'jwtProviders:\n- name: kubernetes\n  issuer: %s\n  audiences: [api.%s.svc]\n' % (issuer, system)
        if issuer in (in_cluster, in_cluster + '.cluster.local'):
            text += ('  certificateAuthorityFile: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt\n'
                     '  discoveryTokenFile: /var/run/secrets/kubernetes.io/serviceaccount/token\n')
        create({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'ate-api-authentication', 'namespace': system},
                'data': {'authentication.yaml': text.rstrip('\n')}})


main()
