"""Render the dedicated Gateway baseline before installing or applying owner instances."""

def resources(p):
    namespace = p['gatewayNamespace']
    result = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': ns}} for ns in dict.fromkeys((p['namespace'], namespace))]
    result.append({'apiVersion': 'gateway.networking.k8s.io/v1', 'kind': 'Gateway',
        'metadata': {'name': p['gatewayName'], 'namespace': namespace}, 'spec': {'gatewayClassName': p['gatewayClass'],
        'listeners': [{'name': p['callerListener'], 'port': p['callerPort'], 'protocol': 'HTTP', 'allowedRoutes': {'namespaces': {'from': 'Selector', 'selector': {'matchLabels': {'kubernetes.io/metadata.name': p['namespace']}}}}},
                      {'name': p['verifyListener'], 'port': p['gatewayPort'], 'protocol': 'HTTP', 'allowedRoutes': {'namespaces': {'from': 'Selector', 'selector': {'matchLabels': {'kubernetes.io/metadata.name': p['namespace']}}}}}]}})
    for suffix, listener, subject in [('verify', p['verifyListener'], 'demo-verifier'), ('caller', p['callerListener'], 'demo-caller')]:
        result.append({'apiVersion': 'agentgateway.dev/v1alpha1', 'kind': 'AgentgatewayPolicy',
            'metadata': {'name': 'classic-listener-' + suffix, 'namespace': namespace},
            'spec': {'targetRefs': [{'group': 'gateway.networking.k8s.io', 'kind': 'Gateway', 'name': p['gatewayName'], 'sectionName': listener}],
                'traffic': {'jwtAuthentication': {'mode': 'Strict', 'preserveToken': False,
                    'providers': [{'issuer': p['issuer'], 'audiences': [p['audience']], 'jwks': {'inline': p['jwks']}}]},
                'authorization': {'action': 'Require', 'policy': {'matchExpressions': ['jwt.sub == "system:serviceaccount:' + p['namespace'] + ':' + subject + '"']}}}}})
    return {'apiVersion': 'v1', 'kind': 'List', 'items': result}
