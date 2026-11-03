"""Render additional boundaries for shared gateway and native control plane."""
import argparse,json
p=argparse.ArgumentParser();p.add_argument('--settings',required=True);a=p.parse_args();s=json.load(open(a.settings))
items=[]
peer=lambda ns,labels={}: {'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':ns}},'podSelector':{'matchLabels':labels}}
def policy(ns,name,selector,spec):items.append({'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':name,'namespace':ns},'spec':{'podSelector':{'matchLabels':selector},**spec}})
for ns in ('secure-byo-hosted','secure-byo-kro'):
 policy(ns,'frontdoor-central-gateway',{'app':'secure-byo-frontdoor'},{'policyTypes':['Ingress','Egress'],
  'ingress':[{'from':[peer('secure-byo-gateway-system',{'gateway.networking.k8s.io/gateway-name':'secure-byo'})],'ports':[{'port':8080}]}],
  'egress':[{'to':[peer('agent-flow-demo',{'app':'flow-gateway'})],'ports':[{'port':8081}]}]})
 policy(ns,'workers-central-gateway',{'ate.dev/worker-pool':'approved-worker'},{'policyTypes':['Egress'],
  'egress':[{'to':[peer('secure-byo-gateway-system',{'gateway.networking.k8s.io/gateway-name':'secure-byo'})],'ports':[{'port':8080 if ns.endswith('hosted') else 8081},{'port':8082 if ns.endswith('hosted') else 8083},{'port':8084}]}]})
policy('kagent','secure-byo-controller-boundary',s.get('controllerSelector',{'app.kubernetes.io/name':'kagent','app.kubernetes.io/component':'controller'}),{'policyTypes':['Ingress'],
 'ingress':[{'from':[peer('kagent'),peer('ate-system',{'app':'atenet-egress'}),peer('secure-byo-gateway-system',{'gateway.networking.k8s.io/gateway-name':'secure-byo'}),peer('agent-flow-demo'),peer('kyverno-recovery-live'),peer('kyverno-dashboard-demo'),*[peer(ns,{'app':'secure-byo-frontdoor'}) for ns in ('secure-byo-hosted','secure-byo-kro')]],'ports':[{'port':8083}]}]})
policy('kagent','secure-byo-native-controller-boundary',{'app':'secure-byo-native-controller'},{'policyTypes':['Ingress'],
 'ingress':[{'from':[peer('kagent'),peer('secure-byo-gateway-system',{'gateway.networking.k8s.io/gateway-name':'secure-byo'}),*[peer(ns,{'app':'secure-byo-frontdoor'}) for ns in ('secure-byo-hosted','secure-byo-kro')]],'ports':[{'port':8083}]}]})
print(json.dumps({'apiVersion':'v1','kind':'List','items':items},indent=2))
