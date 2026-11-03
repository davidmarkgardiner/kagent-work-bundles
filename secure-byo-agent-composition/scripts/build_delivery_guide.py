"""Build offline supporting guides from the delivery and human prerequisite contracts."""
import argparse
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def table_rows(filename, pattern):
    rows = []
    for line in (ROOT / filename).read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if any(re.fullmatch(pattern, cell) for cell in cells):
            rows.append(cells)
    return rows


def text(value):
    return html.escape(value.replace('`', ''))


def build_html(path):
    prerequisites = table_rows('HUMAN-PREREQUISITES.md', r'P\d{2}')
    gates = table_rows('DESIRED-STATE.md', r'D\d{2}')
    inputs = table_rows('DAVID-START-HERE.md', r'Source transfer|Target and authority|Runtime choice|Internal artifacts|Model and content access|Identity and demo scope')
    demo = table_rows('SHOWCASE-DEMO.md', r'[1-8]\. .+')
    if (len(prerequisites), len(gates), len(inputs), len(demo)) != (29, 9, 6, 8):
        raise ValueError('Source guide tables changed; review the supporting guide layout')
    cards = ''.join(f'<article><h3>{text(row[0])}</h3><p>{text(row[1])}</p></article>' for row in inputs)
    gate_html = ''.join(f'<tr><th scope="row">{text(row[0])}</th><td>{text(row[1])}</td><td>{text(row[2])}</td></tr>' for row in gates)
    check_html = ''.join(f'''<div class="checkrow"><label><input type="checkbox" data-id="{row[1]}"><span><b>{row[1]}</b> {text(row[2])}<small>Owner: {text(row[3])}</small></span></label><input class="evidence" data-evidence="{row[1]}" aria-label="{row[1]} private evidence reference" placeholder="Owner / evidence reference / N/A reason"></div>''' for row in prerequisites)
    demo_html = ''.join(f'<li><h3>{text(row[0])}</h3><p>{text(row[1])}</p><small>Retain: {text(row[2])}</small></li>' for row in demo)
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Offline secure BYO Agent delivery guide, human prerequisites and demo rehearsal.">
<title>Secure BYO Agent | Verified delivery</title><style>
:root{--paper:#faf9f5;--ink:#141413;--muted:#53534d;--line:#d1cfc5;--accent:#9b482e;--soft:#eee9de;--green:#405632}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}a{color:var(--accent);text-underline-offset:3px}main{max-width:1160px;margin:auto;padding:52px 30px 72px}.eyebrow{font:12px/1.4 ui-monospace,monospace;letter-spacing:.12em;color:var(--accent)}h1,h2{font-family:Georgia,serif;font-weight:400;letter-spacing:-.025em;line-height:1.08}h1{font-size:clamp(42px,6vw,70px);max-width:850px;margin:18px 0 24px}h2{font-size:36px;margin:0 0 22px}h3{font-size:17px;margin:0 0 8px}p{margin:0 0 16px}header p{max-width:800px;font-size:19px;color:var(--muted)}nav{display:flex;gap:12px 24px;flex-wrap:wrap;padding:22px 0}section{padding:38px 0;border-top:1px solid var(--line)}.notice{border-left:4px solid var(--accent);background:var(--soft);padding:16px 20px;margin:22px 0}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.cards article{border:1px solid var(--line);padding:22px;background:#fff}.cards p{font-size:15px;margin:0}small{display:block;color:var(--muted);font-size:13px;line-height:1.5}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:14px 12px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}thead{background:var(--soft)}th:first-child{white-space:nowrap}.scroll{overflow-x:auto}.fields{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0}label{display:block}label>span{display:block}input:not([type=checkbox]),select,textarea{font:inherit;border:1px solid #aaa89f;padding:10px;background:white;color:var(--ink);border-radius:3px;width:100%;max-width:100%}input:focus,select:focus,textarea:focus,button:focus{outline:3px solid #d9a38c;outline-offset:2px}input[type=checkbox]{width:21px;height:21px;accent-color:var(--green);flex-shrink:0;margin:4px 0}.checkrow{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(200px,1fr);gap:22px;align-items:center;padding:16px 0;border-top:1px solid var(--line)}.checkrow label{display:flex;align-items:flex-start;gap:13px}.checkrow b{font-family:ui-monospace,monospace;font-size:13px}.checkrow small{margin-top:6px}.evidence{font-size:13px!important}.status{font-family:ui-monospace,monospace;color:var(--muted);padding:12px 0}ol{padding-left:26px}ol li{padding:10px 0 16px 10px}ol li p{margin-bottom:4px}.buttons{display:flex;gap:14px;flex-wrap:wrap;margin:20px 0}button{font:600 15px system-ui;border:1px solid var(--ink);background:var(--ink);color:white;padding:12px 18px;border-radius:3px;cursor:pointer}button.secondary{background:white;color:var(--ink)}textarea{min-height:170px;font:12px/1.5 ui-monospace,monospace}.footer{font-size:13px;color:var(--muted)}@media(max-width:760px){main{padding:30px 18px 45px}.cards,.fields{grid-template-columns:1fr}.checkrow{grid-template-columns:1fr;gap:10px}h2{font-size:30px}th,td{padding:10px 8px}table{min-width:580px}}@media print{body{background:#fff;font-size:10pt}main{max-width:none;padding:0}h1{font-size:31pt}h2{font-size:22pt}section{padding:18px 0}nav,.buttons,#export-area{display:none}.cards{grid-template-columns:1fr 1fr}.cards article,.checkrow,tr,ol li{break-inside:avoid}.notice{background:#f4f1ea}a{color:#141413}.fields{grid-template-columns:1fr 1fr}input{border:1px solid #aaa}.scroll{overflow:visible}table{min-width:0}}
</style></head><body><main>
<header><div class="eyebrow">SECURE BYO AGENT / DELIVERY GUIDE</div><h1>Keep going until the outcome is <em>verified.</em></h1><p>Extend the existing HostedAgent work, prove the selected target, and rehearse a demonstration another person can repeat.</p><div class="notice"><strong>Supporting document, not live telemetry.</strong> The native lab proof is separate from workplace delivery. Manual checklist entries do not pass a target gate.</div><nav aria-label="Guide sections"><a href="#inputs">Your inputs</a><a href="#outcome">Delivery gates</a><a href="#checklist">Prerequisite record</a><a href="#demo">Demo rehearsal</a><a href="DELIVERY-GUIDE.pdf">Printable PDF</a></nav></header>
<section id="inputs"><h2>What David provides.</h2><p>The agent handles discovery, compatible reuse, implementation, diagnosis, fixes, verification and rehearsal. You provide the target scope and access that only the relevant owners can supply.</p><div class="cards">__INPUTS__</div><p class="footer">For Flux content bootstrap, ensure reviewed files are already committed and accessible. Supply credential references privately, never secret values. Copy both repository folders.</p></section>
<section id="outcome"><h2>What counts as delivery.</h2><div class="scroll"><table><thead><tr><th>Gate</th><th>Required outcome</th><th>Receipt needed</th></tr></thead><tbody>__GATES__</tbody></table></div><div class="notice"><strong>Implement. Verify. Fix. Rehearse.</strong> Continue within the supplied authority. Preserve failures and rerun affected gates. A blocked external dependency needs an exact owner and action; it is not a pass. Save a private resume checkpoint if the session ends.</div><p>Preserve the four existing CRDs and no-Substrate path. Native actor claims need actual native runtime proof. Do not install Substrate or substitute a Job to bypass a missing native prerequisite.</p></section>
<section id="checklist"><h2>Private prerequisite record.</h2><p>References only. No network requests, autosave or backend. Export the record before closing. Keep completed records private. Blank boxes mean unverified, not necessarily absent.</p><div class="fields"><label>Target / approved scope<input id="target" autocomplete="off"></label><label>Reviewer / date<input id="reviewer" autocomplete="off"></label><label>Runtime path<select id="track"><option value="undecided">Not selected</option><option value="existing-standalone">Existing no-Substrate standalone path</option><option value="approved-native">Approved compatible native path</option></select></label><label>Source revision / authorization reference<input id="revision" autocomplete="off"></label></div><p class="status" id="status" aria-live="polite">0 of 29 items manually reported complete. Target outcome remains unverified.</p>__CHECKS__</section>
<section id="demo"><h2>Rehearse the whole story.</h2><p>Use the final delivered revision and a dedicated approved POC scope. The run sheet targets 8 to 12 minutes. Do not show tokens or call saved receipts fresh execution.</p><ol>__DEMO__</ol><p>After recreation, obtain fresh independent approval and repeat acceptance. Leave the agreed stable state. If rehearsal fails, retain the receipt, fix the cause, and repeat the full rehearsal.</p></section>
<section id="export-area"><h2>Export back to the work agent.</h2><p>This exports a human-reported checklist, not verified outcome evidence. The work agent must attach actual receipts and satisfy the delivery contract.</p><div class="buttons"><button id="download">Export checklist JSON</button><button id="copy" class="secondary">Copy checklist JSON</button><button id="print" class="secondary">Print guide</button></div><label for="record">Export preview and clipboard fallback</label><textarea id="record" readonly></textarea><p id="message" role="status"></p></section>
<footer class="footer"><p>Source contracts: <a href="../DESIRED-STATE.md">desired state</a>, <a href="../DAVID-START-HERE.md">David's inputs</a>, <a href="../HUMAN-PREREQUISITES.md">human sheet</a>, <a href="../WORK-AGENT-PROMPT.md">agent prompt</a>, <a href="../SHOWCASE-DEMO.md">demo run sheet</a>.</p><p>Entra, automatic renewal, cold target imports, ephemeral-container admission and operational exposure requirements need their selected target evidence. No completed existing-operator port or workplace demonstration is implied.</p></footer>
</main><script>
const boxes=[...document.querySelectorAll('input[type=checkbox]')];
const record=()=>({format:'secure-byo-human-checklist-v1',outcome:'unverified',target:document.querySelector('#target').value,reviewer:document.querySelector('#reviewer').value,track:document.querySelector('#track').value,sourceAndAuthorization:document.querySelector('#revision').value,items:boxes.map(box=>({id:box.dataset.id,reportedComplete:box.checked,evidenceReference:document.querySelector('[data-evidence="'+box.dataset.id+'"]').value})),notice:'Manual record only. Actual target receipts and a successful full rehearsal are required.'});
const refresh=()=>{document.querySelector('#status').textContent=boxes.filter(box=>box.checked).length+' of 29 items manually reported complete. Target outcome remains unverified.';document.querySelector('#record').value=JSON.stringify(record(),null,2)};
document.querySelectorAll('input,select').forEach(input=>input.addEventListener('input',refresh));
document.querySelector('#download').addEventListener('click',()=>{refresh();const url=URL.createObjectURL(new Blob([document.querySelector('#record').value],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='secure-byo-private-prerequisites.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);document.querySelector('#message').textContent='Checklist exported. Keep this completed record private.'});
document.querySelector('#copy').addEventListener('click',async()=>{refresh();try{await navigator.clipboard.writeText(document.querySelector('#record').value);document.querySelector('#message').textContent='Checklist copied. Keep it private.'}catch{document.querySelector('#record').focus();document.querySelector('#record').select();document.querySelector('#message').textContent='Clipboard unavailable. Copy the selected JSON manually.'}});
document.querySelector('#print').addEventListener('click',()=>window.print());refresh();
</script></body></html>'''
    for key, value in [('__INPUTS__', cards), ('__GATES__', gate_html), ('__CHECKS__', check_html), ('__DEMO__', demo_html)]:
        template = template.replace(key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template + '\n')


def build_pdf(path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BriefTitle',fontName='Helvetica',fontSize=30,leading=33,spaceAfter=18))
    styles.add(ParagraphStyle(name='BriefHeading',fontName='Helvetica-Bold',fontSize=14,leading=18,spaceBefore=12,spaceAfter=9))
    styles.add(ParagraphStyle(name='BriefBody',fontName='Helvetica',fontSize=10,leading=14,spaceAfter=10))
    styles.add(ParagraphStyle(name='BriefCell',fontName='Helvetica',fontSize=9,leading=12,spaceAfter=0))
    styles.add(ParagraphStyle(name='BriefSmall',fontName='Helvetica',fontSize=8,leading=11,textColor=colors.HexColor('#53534d')))
    story = []
    para = lambda value, style='BriefBody': Paragraph(value, styles[style])
    def table(rows, widths):
        value=Table([[para(text(cell),'BriefCell') for cell in row] for row in rows],colWidths=widths,hAlign='LEFT')
        value.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#d1cfc5'))]))
        return value
    story += [para('SECURE BYO AGENT / DELIVERY BRIEF','BriefSmall'),Spacer(1,14),para('A verified outcome.<br/>A repeatable demonstration.','BriefTitle'),para('Extend the existing HostedAgent operator. Continue through implementation, diagnosis, fixes, target verification and full rehearsal. A plan, a Ready flag or source tests alone do not complete delivery.')]
    gates=table_rows('DESIRED-STATE.md',r'D\d{2}')
    story += [para('Required delivery gates','BriefHeading'),table([[r[0],r[1]] for r in gates],[38,461]),Spacer(1,16),para('Evidence stays tied to the actual target and final revision. Required blocked or skipped gates are not passes. Native claims require native proof; a standalone Job is a different execution path.','BriefSmall'),PageBreak()]
    story += [para('DAVID / INPUTS AND OWNERS','BriefSmall'),Spacer(1,14),para('What you need<br/>to provide.','BriefTitle'),para('You do not need to write the implementation YAML. The agent handles discovery, reuse, builds, manifests, tests, fixes and rehearsal. Supply the access and platform decisions only the relevant owners can provide.')]
    inputs=table_rows('DAVID-START-HERE.md',r'Source transfer|Target and authority|Runtime choice|Internal artifacts|Model and content access|Identity and demo scope')
    story += [table([[r[0],r[1]] for r in inputs],[119,380]),Spacer(1,16),para('Content bootstrap','BriefHeading'),para('If still outstanding, ensure the reviewed sample files are committed and accessible in the permitted repository. Give the agent its URL/ref and approved read access. The agent resolves the exact revision and verifies hashes.'),para('No public pulls from work. Reuse compatible existing builds. Give Secret/CA references through the approved private mechanism, never token or password values.','BriefSmall'),Spacer(1,14),para('Target / scope: __________________________________________','BriefBody'),para('Owner / access reference: _________________________________','BriefBody'),para('Runtime path / decision: __________________________________','BriefBody'),PageBreak()]
    story += [para('PRESENTER / FRESH TARGET RECEIPTS','BriefSmall'),Spacer(1,14),para('Rehearse the<br/>whole story.','BriefTitle'),para('Plan 8 to 12 minutes in a dedicated approved POC scope. Run against the final delivered revision. Do not show credentials or present historical evidence as live execution.')]
    demo=table_rows('SHOWCASE-DEMO.md',r'[1-8]\. .+')
    story += [table([[r[0],r[1]] for r in demo],[132,367]),Spacer(1,14),para('Fix and repeat','BriefHeading'),para('If rehearsal fails, retain the failed receipt, fix its cause and repeat the full rehearsal. Reapprove recreated objects and repeat acceptance. Leave the agreed stable state.'),para('Report verified-demo-ready only when every required target gate and the full rehearsal pass. If blocked, record the exact owner/input and continue independent work. Save a private WORK-STATE checkpoint if a session must hand over.','BriefSmall'),Spacer(1,12),para('Supporting guide only. The existing-operator port, workplace execution and demo are not implied complete. Entra, renewal, cold import, live ephemeral admission and exposure requirements need target evidence.','BriefSmall')]
    def footer(canvas, doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor('#d1cfc5'));canvas.line(48,39,A4[0]-48,39);canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#53534d'));canvas.drawString(48,25,'Secure BYO Agent | DESIRED-STATE.md + HUMAN-PREREQUISITES.md');canvas.drawRightString(A4[0]-48,25,str(doc.page));canvas.restoreState()
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=42,bottomMargin=52,title='Secure BYO Agent - verified delivery and prerequisites',author='Platform engineering',pageCompression=1).build(story,onFirstPage=footer,onLaterPages=footer)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html',type=Path,default=ROOT/'docs/DELIVERY-GUIDE.html')
    parser.add_argument('--pdf',type=Path,default=ROOT/'docs/DELIVERY-GUIDE.pdf')
    args=parser.parse_args()
    build_html(args.html)
    build_pdf(args.pdf)
    print(json.dumps({'html':str(args.html),'pdf':str(args.pdf)}))
