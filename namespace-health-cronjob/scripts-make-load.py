"""Emit 100 disposable low-resource Pods for the declared pilot sizing test."""
import sys
import yaml
for suffix in 'abcde':
    for number in range(20):
        doc={'apiVersion':'v1','kind':'Pod','metadata':{'name':f'load-{number:02d}','namespace':f'health-fixture-{suffix}','labels':{'app.kubernetes.io/part-of':'namespace-health-trial','app':'namespace-health-load'}},'spec':{'terminationGracePeriodSeconds':0,'containers':[{'name':'app','image':'busybox:1.37.0','command':['sh','-c','sleep 7200'],'resources':{'requests':{'cpu':'1m','memory':'4Mi'},'limits':{'cpu':'50m','memory':'16Mi'}}}]}}
        yaml.safe_dump(doc,sys.stdout,sort_keys=False)
        sys.stdout.write('---\n')
