"""Verify the exported slides, local links, provenance and copied-file integrity."""
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('src', 'href', 'poster', 'data-composition-src'):
            if attrs.get(key):
                self.refs.append((tag, attrs.get('rel', ''), attrs[key]))


errors = []
html_count = 0
for source in ROOT.rglob('*.html'):
    html_count += 1
    links = Links()
    links.feed(source.read_text())
    for tag, rel, raw in links.refs:
        url = urlsplit(raw)
        if url.scheme == 'file':
            errors.append('Machine-local file link: ' + str(source.relative_to(ROOT)))
            continue
        if url.scheme or url.netloc:
            if url.scheme != 'data' and (tag in ('script', 'img', 'iframe') or (tag == 'link' and 'stylesheet' in rel)):
                errors.append('External runtime asset: ' + raw)
            continue
        if not url.path:
            continue
        # HyperFrames subcompositions resolve media against the project root.
        base = ROOT/'original-video' if source.parent == ROOT/'original-video/compositions' else source.parent
        target = (base / unquote(url.path)).resolve()
        if not target.is_relative_to(ROOT) or not target.exists():
            errors.append(str(source.relative_to(ROOT)) + ' missing local reference ' + raw)

for source in ROOT.rglob('*.md'):
    if 'previous' in source.relative_to(ROOT).parts:
        continue
    for raw in re.findall(r'\]\(([^)]+)\)', source.read_text()):
        url = urlsplit(raw)
        if url.scheme or url.netloc or not url.path:
            continue
        target = (source.parent / unquote(url.path)).resolve()
        if not target.is_relative_to(ROOT) or not target.exists():
            errors.append(str(source.relative_to(ROOT)) + ' missing local reference ' + raw)

for source in ROOT.rglob('*.svg'):
    try:
        ET.parse(source)
    except ET.ParseError:
        errors.append('Invalid SVG XML: ' + str(source.relative_to(ROOT)))

manifest = json.loads((ROOT/'slides/SOURCE-MANIFEST.json').read_text())
for entry in manifest['files']:
    target = ROOT / entry['path']
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != entry['sha256']:
        errors.append('Copied source hash mismatch: ' + entry['path'])

media = json.loads((ROOT/'MEDIA-MANIFEST.json').read_text())
media_paths = set()
for entry in media['files']:
    target = (ROOT / entry['path']).resolve()
    if not target.is_relative_to(ROOT) or not target.is_file():
        errors.append('Missing original media/source: ' + entry['path'])
        continue
    media_paths.add(target)
    with target.open('rb') as stream:
        hasher = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
        digest = hasher.hexdigest()
    if target.stat().st_size != entry['bytes'] or digest != entry['sha256']:
        errors.append('Original media/source hash mismatch: ' + entry['path'])
    if target.stat().st_size >= 100 * 1024 * 1024:
        errors.append('File exceeds normal GitHub blob limit: ' + entry['path'])

rfc1918 = [ipaddress.ip_network(x) for x in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
for source in ROOT.rglob('*'):
    if not source.is_file() or '__pycache__' in source.parts or source.name == 'verify-bundle.py':
        continue
    try:
        text = source.read_text()
    except UnicodeDecodeError:
        if source.resolve() not in media_paths:
            errors.append('Unmanifested binary artifact: ' + str(source.relative_to(ROOT)))
        continue
    for value in re.findall(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])', text):
        try:
            addr = ipaddress.ip_address(value)
        except ValueError:
            continue
        if any(addr in network for network in rfc1918):
            errors.append('RFC1918 address in ' + str(source.relative_to(ROOT)))

print(json.dumps({'passed':not errors,'htmlFiles':html_count,'copiedFilesVerified':len(manifest['files']),
                  'originalMediaSourceFilesVerified':len(media['files']),
                  'mainPresentationEntries':manifest['mainPresentations'],'errors':errors},indent=2))
raise SystemExit(1 if errors else 0)
