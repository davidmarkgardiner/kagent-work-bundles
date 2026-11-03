"""Render a protected scoped lab gateway using discovered public signing keys."""
import argparse,json
p=argparse.ArgumentParser();p.add_argument('--jwks',required=True);p.add_argument('--issuer',required=True);a=p.parse_args()
ns='secure-byo-gateway-system';meta=lambda name:{'name':name,'namespace':ns}
items=[{'apiVersion':'gateway.networking.k8s.io/v1','kind':'Gateway','metadata':meta('secure-byo'),'spec':{'gatewayClassName':'agentgateway','listeners':[{'name':lane,'port':port,'protocol':'HTTP','allowedRoutes':{'namespaces':{'from':'Same'}}} for lane,port in [('hosted',8080),('kro',8081),('hosted-model',8082),('kro-model',8083),('runtime',8084)]]}}]
for lane in ('hosted','kro'):
 team='secure-byo-'+lane
 subjects=['system:serviceaccount:'+team+':'+s for s in ('approved-caller','approved-worker')]
 policy={'apiVersion':'agentgateway.dev/v1alpha1','kind':'AgentgatewayPolicy','metadata':meta(team),'spec':{'targetRefs':[{'group':'gateway.networking.k8s.io','kind':'HTTPRoute','name':team}], 'traffic':{'jwtAuthentication':{'mode':'Strict','preserveToken':True,'providers':[{'issuer':a.issuer,'audiences':['secure-byo'],'jwks':{'inline':json.dumps(json.load(open(a.jwks)))}}]},'authorization':{'action':'Require','policy':{'matchExpressions':['jwt.sub in '+json.dumps(subjects)]}}}}}
 items.append(policy)
 model_policy=json.loads(json.dumps(policy));model_policy['metadata']['name']=team+'-model';model_policy['spec']['targetRefs'][0]['name']=team+'-model';items.append(model_policy)
runtime_methods = [('TaskStoreService', m) for m in ('CreateTask','GetTask','UpdateTask','SettleTask','ListTasks')]
runtime_methods += [('MemoryService', m) for m in ('AddSession','AddSessionBatch','Search')]
items += [
 {'apiVersion':'v1','kind':'Service','metadata':{'name':'secure-byo-runtime-backend','namespace':'kagent'},'spec':{'selector':{'app':'secure-byo-native-controller'},'ports':[{'name':'grpc','port':8083,'targetPort':8083,'appProtocol':'kubernetes.io/h2c'}]}},
 {'apiVersion':'gateway.networking.k8s.io/v1beta1','kind':'ReferenceGrant','metadata':{'name':'secure-byo-runtime','namespace':'kagent'},'spec':{'from':[{'group':'gateway.networking.k8s.io','kind':'GRPCRoute','namespace':ns}],'to':[{'group':'','kind':'Service','name':'secure-byo-runtime-backend'}]}},
 {'apiVersion':'gateway.networking.k8s.io/v1','kind':'GRPCRoute','metadata':meta('secure-byo-runtime'),'spec':{'parentRefs':[{'name':'secure-byo','sectionName':'runtime'}],'rules':[{'matches':[{'method':{'type':'Exact','service':'kagent.runtime.v1.'+service,'method':method}} for service,method in runtime_methods],'backendRefs':[{'name':'secure-byo-runtime-backend','namespace':'kagent','port':8083}]}]}}
]
print(json.dumps({'apiVersion':'v1','kind':'List','items':items},indent=2))
