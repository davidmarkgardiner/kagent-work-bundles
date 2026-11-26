#!/usr/bin/env python3
"""SigV4 PUT of one file, so the jumpbox needs no aws CLI.
Usage: s3put.py <endpoint> <bucket/key> <file>; credentials from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY."""
import datetime, hashlib, hmac, os, sys, urllib.parse, urllib.request

endpoint, path, name = sys.argv[1:4]
body = open(name, 'rb').read()
access, key = os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY']
now = datetime.datetime.now(datetime.timezone.utc)
stamp, day = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
host = urllib.parse.urlparse(endpoint).netloc
uri = '/' + urllib.parse.quote(path)
digest = hashlib.sha256(body).hexdigest()
signed = 'host;x-amz-content-sha256;x-amz-date'
canonical = '\n'.join(['PUT', uri, '', 'host:' + host, 'x-amz-content-sha256:' + digest, 'x-amz-date:' + stamp, '', signed, digest])
scope = day + '/us-east-1/s3/aws4_request'
to_sign = '\n'.join(['AWS4-HMAC-SHA256', stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
k = ('AWS4' + key).encode()
for part in (day, 'us-east-1', 's3', 'aws4_request'):
    k = hmac.new(k, part.encode(), hashlib.sha256).digest()
signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
req = urllib.request.Request(endpoint + uri, data=body, method='PUT', headers={
    'x-amz-content-sha256': digest, 'x-amz-date': stamp,
    'Authorization': 'AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s' % (access, scope, signed, signature)})
urllib.request.urlopen(req, timeout=600).read()
print('uploaded', path)
