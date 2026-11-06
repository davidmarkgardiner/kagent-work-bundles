import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
source = ROOT / 'demo/sre-lens-data.json'
if not source.exists():
    raise SystemExit('Missing demo/sre-lens-data.json')
data = json.loads(source.read_text())
template = (ROOT / 'triage.html').read_text()
match = re.search(r'(<script type="application/json" id="deckData">)(.*?)(</script>)', template, re.S)
assert match, 'The reference deck must contain deckData'
encoded = json.dumps(data, ensure_ascii=False, indent=2).replace('<', '\\u003c')
html = template[:match.start(2)] + encoded + template[match.end(2):]
html = re.sub(r'<title>.*?</title>', '<title>SRE Lens asks the right specialists | Interactive architecture</title>', html, count=1)
(ROOT / 'sre-lens.html').write_text(html)
print('Built SRE Lens with', len(data['slides']), 'illustrated slides.')
