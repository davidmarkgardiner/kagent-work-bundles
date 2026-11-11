"""Render the recording script as an offline, readable page with copyable commands."""
from html import escape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def inline(text):
    text = escape(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'\[([^]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)


lines = (ROOT/'RECORDING-WALKTHROUGH.md').read_text().splitlines()
body = []
paragraph = []
code = None
section = 0


def flush():
    if paragraph:
        body.append('<p>' + inline(' '.join(paragraph)) + '</p>')
        paragraph.clear()


for line in lines:
    if line.startswith('```'):
        flush()
        if code is None:
            code = []
        else:
            body.append('<div class="command"><button type="button">Copy commands</button><pre><code>' + escape('\n'.join(code)) + '</code></pre></div>')
            code = None
        continue
    if code is not None:
        code.append(line)
    elif line.startswith('## '):
        flush()
        section += 1
        body.append(f'<h2 id="step-{section}">' + inline(line[3:]) + '</h2>')
    elif line.startswith('# '):
        flush()
        body.append('<h1>' + inline(line[2:]) + '</h1>')
    elif line.startswith('> '):
        flush()
        body.append('<blockquote>' + inline(line[2:]) + '</blockquote>')
    elif re.match(r'^\d+\. ', line):
        flush()
        body.append('<p class="click">' + inline(line) + '</p>')
    elif not line.strip():
        flush()
    else:
        paragraph.append(line)
flush()
head = '''<!doctype html><html lang="en-GB"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DICE recording script</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#F4F3EE;color:#1C1C1C;font:18px/1.65 Arial,Helvetica,sans-serif}main{max-width:1040px;margin:auto;padding:36px 32px 100px}nav{display:flex;gap:24px;flex-wrap:wrap}a{color:#A90000;text-underline-offset:4px}h1{font-size:48px;line-height:1.12;font-weight:400;margin:50px 0 30px}h2{font-size:30px;font-weight:400;line-height:1.3;border-top:2px solid #E60000;padding-top:24px;margin:72px 0 24px;scroll-margin-top:24px}blockquote{margin:24px 0;padding:24px 28px;background:white;border-left:4px solid #E60000;font-size:21px}.command{position:relative;background:#fff;border:1px solid #CCCABC;margin:24px 0;padding-top:48px}pre{margin:0;padding:20px;overflow:auto;font:15px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace}p code{font-size:.9em;background:#eae8e1;padding:2px 4px;overflow-wrap:anywhere}button{position:absolute;right:12px;top:12px;background:#1C1C1C;color:white;border:0;border-radius:3px;padding:8px 14px;font:14px Arial;cursor:pointer}button:focus-visible,a:focus-visible{outline:3px solid #E60000;outline-offset:4px}.intro{padding:20px 24px;background:#fff;border-top:3px solid #E60000}.click{padding-left:18px;border-left:2px solid #CCCABC}@media print{body{font-size:11pt}main{padding:0}button,nav{display:none}pre{white-space:pre-wrap;font-size:9pt}blockquote{break-inside:avoid}h2{break-after:avoid}}
</style><main><nav><a href="START-HERE.html">Start here</a><a href="RECORDING-WALKTHROUGH.md">Markdown source</a><a href="WORK-AGENT-PROMPT.md">Work-agent handoff</a></nav><p class="intro">Read the quoted text aloud. Paste each command block at its numbered step. The workplace agent first resolves and rehearses your private copy; this public template contains environment placeholders.</p>'''
script = '''</main><script>document.querySelectorAll('.command button').forEach(button=>button.addEventListener('click',async()=>{const code=button.parentElement.querySelector('code');try{await navigator.clipboard.writeText(code.textContent);button.textContent='Copied';setTimeout(()=>button.textContent='Copy commands',1800)}catch(error){const selection=window.getSelection();const range=document.createRange();range.selectNodeContents(code);selection.removeAllRanges();selection.addRange(range);button.textContent='Selected — copy with keyboard'}}));</script></html>'''
(ROOT/'recording.html').write_text(head+'\n'.join(body)+script)
print('Wrote recording.html')
