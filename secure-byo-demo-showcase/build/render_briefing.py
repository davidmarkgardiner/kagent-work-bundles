"""Render the same briefing content as offline HTML and a six-page PDF."""
import argparse
from html import escape
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--html-only', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
content = json.loads((root / 'briefing.json').read_text())
diagram = '''<figure><svg viewBox="0 0 980 135" role="img" aria-labelledby="flow-title">
<title id="flow-title">Target flow from one owner YAML through operator, secured runtime and GoldenScenario to approved access</title>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#7856c8"/></marker></defs>
<g fill="#f5f1fc" stroke="#7856c8" stroke-width="1.5"><rect x="2" y="22" width="170" height="70" rx="8"/><rect x="204" y="22" width="170" height="70" rx="8"/><rect x="406" y="22" width="170" height="70" rx="8"/><rect x="608" y="22" width="170" height="70" rx="8"/><rect x="810" y="22" width="168" height="70" rx="8"/></g>
<g stroke="#7856c8" stroke-width="2" marker-end="url(#arrow)"><path d="M176 57 H199"/><path d="M378 57 H401"/><path d="M580 57 H603"/><path d="M782 57 H805"/></g>
<g text-anchor="middle" fill="#292332" font-family="system-ui,sans-serif" font-size="15"><text x="87" y="52">Owner YAML</text><text x="87" y="74">approved choices</text><text x="289" y="52">Operator</text><text x="289" y="74">bindings + controls</text><text x="491" y="52">Secured runtime</text><text x="491" y="74">Gateway + JWT</text><text x="693" y="52">GoldenScenario</text><text x="693" y="74">actual verification</text><text x="894" y="52">Approved access</text><text x="894" y="74">current evidence</text></g>
</svg><figcaption>Target architecture, not a live status display.</figcaption></figure>'''
style = '''
:root{--ink:#292332;--muted:#625c6b;--purple:#6944ad;--paper:#faf9f6;--line:#ddd7e5;--amber:#825400}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:18px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
a{color:var(--purple)}header{max-width:1180px;margin:auto;padding:24px 40px;border-bottom:1px solid var(--line);display:flex;gap:16px;justify-content:space-between;flex-wrap:wrap;font-size:14px}
.tag{padding:4px 10px;border:1px solid #c9b7e7;border-radius:4px;color:var(--purple);font-size:13px;white-space:nowrap}.page{max-width:1180px;margin:auto;padding:60px 40px;border-bottom:1px solid var(--line)}
.eyebrow{font:13px/1.4 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.1em;color:var(--purple)}h1,h2{font-family:ui-serif,Georgia,serif;font-weight:500;line-height:1.08;letter-spacing:-.025em;max-width:900px;font-size:clamp(34px,5vw,60px);margin:20px 0 24px}
.lead{max-width:940px;font-size:clamp(19px,2.1vw,25px);line-height:1.45}.points{padding:0;list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:14px 28px;margin:32px 0}.points li{padding:18px 0;border-top:2px solid var(--line)}
.note{font-size:15px;color:var(--muted);border-left:3px solid var(--purple);padding-left:18px;max-width:1000px}.scope{color:var(--amber);font-weight:600}figure{margin:28px 0}svg{width:100%;height:auto;display:block}figcaption{font-size:13px;color:var(--muted)}
footer{max-width:1180px;margin:auto;padding:32px 40px 60px;font-size:15px}nav{display:flex;gap:18px;flex-wrap:wrap} @media(max-width:650px){header,.page,footer{padding-left:22px;padding-right:22px}.page{padding-top:36px;padding-bottom:36px}.points{grid-template-columns:1fr;gap:0}svg{min-width:800px}figure{overflow:auto}.tag{white-space:normal}}
@page{size:A4 landscape;margin:12mm}@media print{body{background:white;font-size:13px;line-height:1.4}header,footer{display:none}.page{break-after:page;padding:5mm 2mm;border:none;max-width:none}.page:last-of-type{break-after:auto}h1,h2{font-size:34px;margin:12px 0}.lead{font-size:18px}.points{margin:18px 0;gap:8px 20px}.points li{padding:10px 0}.note{font-size:12px}figure{overflow:visible;margin:12px 0}svg{min-width:0;max-height:100px}.eyebrow{font-size:11px}}
'''
sections = []
for index, page in enumerate(content['pages']):
    heading = 'h1' if index == 0 else 'h2'
    sections.append('<section class="page" id="page-' + str(index + 1) + '"><p class="eyebrow">' + escape(page['eyebrow']) + '</p><' + heading + '>' + escape(page['title']) + '</' + heading + '><p class="lead">' + escape(page['lead']) + '</p>' + (diagram if index == 1 else '') + '<ul class="points">' + ''.join('<li>' + escape(text) + '</li>' for text in page['bullets']) + '</ul><p class="note">' + escape(page['note']) + '</p></section>')
html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'; form-action \'none\'"><title>' + escape(content['title']) + '</title><style>' + style + '</style></head><body><header><span>Secure BYO Agent / Team briefing</span><span class="tag">Without Substrate</span><span class="scope">Office outcome awaits verification</span></header>' + ''.join(sections) + '<footer><nav><a href="SHOWCASE.pdf">Printable PDF</a><a href="PRESENTER-WALKTHROUGH.md">Presenter walkthrough</a><a href="WORK-AGENT-HANDOVER.md">Work-agent handover</a><a href="TEAM-HANDOVER-TEMPLATE.md">Completion report</a></nav><p>This offline briefing makes no network requests and is not the live evidence dashboard. Open the existing approved view for actual observations.</p></footer></body></html>'
(root / 'SHOWCASE.html').write_text(html)
if args.html_only:
    raise SystemExit(0)

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

width, height = landscape(A4)
pdf = canvas.Canvas(str(root / 'SHOWCASE.pdf'), pagesize=(width, height), pageCompression=1)
pdf.setTitle(content['title'])
pdf.setAuthor('Secure BYO Agent project')
styles = {
    'title': ParagraphStyle('title', fontName='Times-Roman', fontSize=36, leading=39, textColor=colors.HexColor('#292332')),
    'lead': ParagraphStyle('lead', fontName='Helvetica', fontSize=17, leading=23, textColor=colors.HexColor('#292332')),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=14, leading=19, textColor=colors.HexColor('#292332'), leftIndent=12, firstLineIndent=-12),
    'note': ParagraphStyle('note', fontName='Helvetica', fontSize=11, leading=15, textColor=colors.HexColor('#625c6b')),
}
for index, page in enumerate(content['pages']):
    pdf.setFillColor(colors.HexColor('#6944ad'))
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(44, height - 32, 'SECURE BYO AGENT  /  WITHOUT SUBSTRATE')
    pdf.setFillColor(colors.HexColor('#825400'))
    pdf.setFont('Helvetica', 9)
    pdf.drawRightString(width - 44, height - 32, 'Office target: not yet verified')
    y = height - 66
    for text, style, gap in [(page['eyebrow'], 'note', 12), (page['title'], 'title', 17), (page['lead'], 'lead', 20)]:
        paragraph = Paragraph(escape(text), styles[style])
        _, block_height = paragraph.wrap(width - 88, height)
        y -= block_height
        paragraph.drawOn(pdf, 44, y)
        y -= gap
    for text in page['bullets']:
        paragraph = Paragraph('- ' + escape(text), styles['body'])
        _, block_height = paragraph.wrap(width - 100, height)
        y -= block_height
        paragraph.drawOn(pdf, 48, y)
        y -= 12
    paragraph = Paragraph(escape(page['note']), styles['note'])
    _, note_height = paragraph.wrap(width - 88, height)
    if y - note_height < 42:
        raise ValueError('Page content exceeds safe footer boundary: ' + page['eyebrow'])
    paragraph.drawOn(pdf, 44, y - note_height - 5)
    if index == 1:
        labels = [('Owner YAML', 'approved choices'), ('Operator', 'bindings + controls'), ('Secured runtime', 'Gateway + JWT'), ('GoldenScenario', 'actual verification'), ('Approved access', 'current evidence')]
        gap = 12
        box_width = (width - 88 - gap * 4) / 5
        box_y = 86
        for step, (title, detail) in enumerate(labels):
            box_x = 44 + step * (box_width + gap)
            pdf.setFillColor(colors.HexColor('#f5f1fc'))
            pdf.setStrokeColor(colors.HexColor('#7856c8'))
            pdf.roundRect(box_x, box_y, box_width, 54, 5, fill=1, stroke=1)
            pdf.setFillColor(colors.HexColor('#292332'))
            pdf.setFont('Helvetica-Bold', 10)
            pdf.drawCentredString(box_x + box_width / 2, box_y + 31, title)
            pdf.setFont('Helvetica', 9)
            pdf.drawCentredString(box_x + box_width / 2, box_y + 16, detail)
            if step < len(labels) - 1:
                pdf.setStrokeColor(colors.HexColor('#7856c8'))
                start = box_x + box_width + 2
                end = start + gap - 4
                pdf.line(start, box_y + 27, end, box_y + 27)
                pdf.line(end - 3, box_y + 30, end, box_y + 27)
                pdf.line(end - 3, box_y + 24, end, box_y + 27)
    pdf.setStrokeColor(colors.HexColor('#ddd7e5'))
    pdf.line(44, 32, width - 44, 32)
    pdf.setFillColor(colors.HexColor('#625c6b'))
    pdf.setFont('Helvetica', 9)
    pdf.drawString(44, 19, 'Prepared briefing. Live acceptance requires current target receipts.')
    pdf.drawRightString(width - 44, 19, str(index + 1) + ' / ' + str(len(content['pages'])))
    pdf.showPage()
pdf.save()
print(json.dumps({'html': 'SHOWCASE.html', 'pdf': 'SHOWCASE.pdf', 'pages': len(content['pages']), 'liveDashboard': False}))
