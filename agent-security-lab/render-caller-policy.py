#!/usr/bin/env python3
"""Render a lab caller policy using the cluster's public issuer and JWKS."""
import json
import subprocess
import sys

if len(sys.argv) != 3 or sys.argv[2] != 'kind-agent-tls':
    raise SystemExit('Usage: render-caller-policy.py LAB_KUBECONFIG kind-agent-tls')
base = ['kubectl', '--kubeconfig', sys.argv[1], '--context', sys.argv[2], 'get', '--raw']
issuer = json.loads(subprocess.check_output(base + ['/.well-known/openid-configuration']))['issuer']
jwks = json.loads(subprocess.check_output(base + ['/openid/v1/jwks']))
policy = {'apiVersion':'agentgateway.dev/v1alpha1','kind':'AgentgatewayPolicy',
 'metadata':{'name':'tls-agent-caller-auth','namespace':'kagent'},
 'spec':{'targetRefs':[{'group':'gateway.networking.k8s.io','kind':'Gateway','name':'tls-agent-gateway','sectionName':'https'}],
 'traffic':{'jwtAuthentication':{'mode':'Strict','preserveToken':False,'providers':[{'issuer':issuer,'audiences':['tls-lab-agent'],'jwks':{'inline':json.dumps(jwks,separators=(',',':'))}}]},
 'authorization':{'action':'Require','policy':{'matchExpressions':['jwt.sub == "system:serviceaccount:kagent:tls-lab-caller"']}}}}}
json.dump(policy,sys.stdout)
