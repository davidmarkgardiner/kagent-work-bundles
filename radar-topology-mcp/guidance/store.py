"""Exact workload-to-guidance bindings. No network, SQL, or filesystem tools."""
import datetime as dt
import json
import re

MAX_CONTENT_BYTES = 4096
MAX_ENVELOPE_BYTES = 16384
MAX_REFERENCES = 5
STABLE_KINDS = {'Deployment', 'StatefulSet', 'DaemonSet', 'CronJob'}


class GuidanceStore:
    def __init__(self, catalog, today=None):
        self.today = today or dt.date.today
        self.bindings = {}
        self.documents = {}
        if catalog['version'] != 1:
            raise ValueError('Unsupported catalog version')
        for doc in catalog['documents']:
            identifier = doc['id']
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', identifier):
                raise ValueError('Invalid reference ID')
            if identifier in self.documents:
                raise ValueError('Duplicate reference ID')
            if doc['type'] not in {'skill', 'runbook', 'knowledge', 'rubric'}:
                raise ValueError('Invalid guidance type')
            for field in ('title', 'source_uri', 'revision', 'applicability', 'reviewed_by'):
                if not isinstance(doc[field], str) or not doc[field] or len(doc[field]) > 512:
                    raise ValueError('Missing or oversized provenance: ' + field)
            reviewed = dt.date.fromisoformat(doc['reviewed_on'])
            expires = dt.date.fromisoformat(doc['review_after'])
            if expires < reviewed:
                raise ValueError('Review dates out of order')
            if len(doc['content'].encode()) > MAX_CONTENT_BYTES:
                raise ValueError('Document exceeds content budget; prepare a reviewed excerpt')
            self.documents[identifier] = dict(doc)
        for binding in catalog['bindings']:
            key = self.identity(**binding['target'])
            if key in self.bindings:
                raise ValueError('Duplicate workload binding')
            refs = binding['references']
            if len(set(refs)) != len(refs) or any(ref not in self.documents for ref in refs):
                raise ValueError('Duplicate or missing reference')
            self.bindings[key] = tuple(refs)

    @staticmethod
    def identity(cluster, namespace, kind, name):
        if kind not in STABLE_KINDS:
            raise ValueError('Resolve Pod/ReplicaSet to its observed stable workload first')
        for value in (cluster, namespace, name):
            if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,252}', value):
                raise ValueError('Invalid identity')
        return cluster, namespace, kind, name

    def metadata(self, doc):
        data = {k: v for k, v in doc.items() if k != 'content'}
        today = self.today()
        data['stale'] = today > dt.date.fromisoformat(doc['review_after'])
        data['review_in_future'] = today < dt.date.fromisoformat(doc['reviewed_on'])
        return data

    @staticmethod
    def bounded(result):
        # Bound both copies, JSON escaping and the JSON-RPC envelope. The
        # conservative escaped text estimate also covers SDK pretty-printing.
        text = json.dumps(result, ensure_ascii=True, indent=2)
        envelope = {'jsonrpc': '2.0', 'id': 'x' * 128,
                    'result': {'content': [{'type': 'text', 'text': text}],
                               'structuredContent': result, 'isError': False}}
        if len(json.dumps(envelope, ensure_ascii=True).encode()) > MAX_ENVELOPE_BYTES - 512:
            return {'status': 'budget_exceeded', 'truncated': True,
                    'message': 'Prepare smaller reviewed guidance; no paging or export.'}
        return result

    def find(self, cluster, namespace, kind, name, limit=5):
        if type(limit) is not int or not 1 <= limit <= MAX_REFERENCES:
            raise ValueError('limit must be an integer between 1 and 5')
        key = self.identity(cluster, namespace, kind, name)
        refs = self.bindings.get(key, ())
        return self.bounded({'status': 'matched' if refs else 'no_binding',
                             'target': dict(zip(('cluster', 'namespace', 'kind', 'name'), key)),
                             'references': [self.metadata(self.documents[r]) for r in refs[:limit]],
                             'total': len(refs), 'truncated': len(refs) > limit})

    def read(self, cluster, namespace, kind, name, reference_id):
        key = self.identity(cluster, namespace, kind, name)
        if reference_id not in self.bindings.get(key, ()):
            return {'status': 'not_bound', 'truncated': False}
        doc = self.documents[reference_id]
        metadata = self.metadata(doc)
        if metadata['stale'] or metadata['review_in_future']:
            return self.bounded({'status': 'review_required', 'reference': metadata,
                                 'truncated': False})
        return self.bounded({'status': 'ok', 'reference': metadata,
                             'content': doc['content'], 'truncated': False})
