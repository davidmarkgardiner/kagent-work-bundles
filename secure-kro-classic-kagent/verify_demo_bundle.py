"""Check offline demo links, embedded theme and package file hashes."""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
PRIMARY = ['START-HERE.html', 'journey.html', 'sre-lens.html', 'triage.html', 'sdlc.html', 'showcase.html', 'resources.html', 'tomorrow.html', 'presentation.html', 'index.html']


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.assets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for key in ['href', 'src']:
            if values.get(key):
                self.links.append(values[key])
        if values.get('src') or tag == 'link' and values.get('rel') == 'stylesheet':
            self.assets.append(values.get('src') or values.get('href'))


def verify():
    errors = []
    theme = (ROOT / 'demo-theme.css').read_text()
    html_files = [p for p in ROOT.rglob('*.html') if p.parent.name != 'demo']
    for page in html_files:
        text = page.read_text()
        document = Document()
        document.feed(text)
        for value in document.links:
            url = urlsplit(value)
            if url.scheme == 'file':
                errors.append(str(page.relative_to(ROOT)) + ': absolute file URL')
            elif not url.scheme and not url.netloc and url.path:
                target = (page.parent / unquote(url.path)).resolve()
                if not target.is_relative_to(ROOT) or not target.exists():
                    errors.append(str(page.relative_to(ROOT)) + ': unavailable ' + value)
        for value in document.assets:
            if urlsplit(value).scheme in {'http', 'https'} or value.startswith('//'):
                errors.append(str(page.relative_to(ROOT)) + ': online runtime asset ' + value)
        if page.parent == ROOT and page.name in PRIMARY:
            if '<style id="dice-bundle-theme">\n' + theme + '\n</style>' not in text:
                errors.append(page.name + ': theme differs')
            match = re.search(r'id="deckData">(.*?)</script>', text, re.S)
            if match:
                data = json.loads(match.group(1))
                for link in data.get('deckLinks', []):
                    if not (ROOT / urlsplit(link['href']).path).is_file():
                        errors.append(page.name + ': missing chapter link ' + link['href'])
    lens = json.loads(re.search(r'id="deckData">(.*?)</script>', (ROOT / 'sre-lens.html').read_text(), re.S).group(1))
    if [slide['id'] for slide in lens['slides']] != ['route', 'reads', 'receipts', 'consume']:
        errors.append('Unexpected SRE Lens chapters')
    for slide in lens['slides']:
        for node in slide['nodes']:
            if node['source'] not in lens['sources']:
                errors.append('Missing Lens source: ' + node['source'])
    journey = json.loads(re.search(r'id="deckData">(.*?)</script>', (ROOT / 'journey.html').read_text(), re.S).group(1))
    order = [slide['id'] for slide in journey['slides']]
    if order != ['intro', 'compare', 'lifecycle', 'resource-purpose', 'hardening', 'tools', 'skills', 'gateway', 'telemetry']:
        errors.append('Unexpected Journey order')
    if errors:
        raise SystemExit('\n'.join(errors))
    manifest = ROOT / 'DEMO-FILES.sha256'
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            expected, name = line.split('  ', 1)
            file = ROOT / name
            if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                raise SystemExit('Package hash mismatch: ' + name)
    print(json.dumps({'passed': True, 'primaryPages': len(PRIMARY), 'htmlPages': len(html_files), 'journeyOrder': order, 'hashManifestChecked': manifest.exists()}))


if __name__ == '__main__':
    verify()
