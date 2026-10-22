#!/usr/bin/env python3
"""Check the reviewed live revision immediately before approved GitOps promotion."""
import argparse
import json
from ordinary_demo import get
from package import slug


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',required=True);parser.add_argument('--preconditions',required=True)
    args=parser.parse_args()
    with open(args.preconditions) as stream:document=json.load(stream)
    if not slug(document.get('namespace')):
        raise ValueError('UnexpectedReviewNamespace')
    expected={('v1','configmaps','hosted-agent-code'),('rbac.authorization.k8s.io/v1','roles','hosted-agent-adapter'),
        ('apps/v1','deployments','hosted-agent-adapter'),('apiextensions.k8s.io/v1','customresourcedefinitions','hostedagents.skills.platform.kagent.dev')}
    actual={(o['apiVersion'],o['plural'],o['name']) for o in document['objects']}
    if actual!=expected or len(document['objects'])!=4:raise ValueError('UnexpectedReviewPreconditionSet')
    for obj in document['objects']:
        if obj['namespace']!=('' if obj['plural']=='customresourcedefinitions' else document['namespace']):
            raise ValueError('UnexpectedReviewNamespace')
        current=get(args.context,obj['namespace'],obj['apiVersion'],obj['plural'],obj['name'])
        if any(current['metadata'].get(k)!=obj[k] for k in ('uid','resourceVersion')):
            raise ValueError('LiveReviewRevisionChanged: rerender/review before promotion')
    print(json.dumps({'reviewedRevisionsUnchanged':True,'objects':4,'atomicCompareAndSwap':False,'applied':False}))


if __name__=='__main__':main()
