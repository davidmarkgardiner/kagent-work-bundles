#!/usr/bin/env python3
"""stdin -> stdout. Shrinks the upstream PostgreSQL requests (sized for load) and sets a StorageClass.
Text edits only, so no PyYAML is needed."""
import re, sys

text, storage_class = sys.stdin.read(), (sys.argv[1] if len(sys.argv) > 1 else '')
text, n = re.subn(r'(requests:\n\s+cpu: )"2"(\n\s+memory: )"1Gi"(\n\s+limits:\n\s+cpu: )"16"', r'\g<1>"250m"\g<2>"1Gi"\g<3>"2"', text)
if n != 1:
    sys.exit('size-postgres: upstream resources block changed')
if storage_class:
    text, n = re.subn(r'(\n(\s+)accessModes:)', r'\n\2storageClassName: %s\1' % storage_class, text)
    if n != 1:
        sys.exit('size-postgres: could not set storageClassName')
sys.stdout.write(text)
