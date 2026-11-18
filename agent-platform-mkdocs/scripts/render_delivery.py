#!/usr/bin/env python3
"""Render stakeholder pages from reviewed YAML; --check refuses stale output."""
import argparse
from datetime import date
from html import escape
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent


def period_order(value):
    year, part = value.split('-')
    month = (int(part[1:]) - 1) * 3 + 1 if part.startswith('Q') else int(part)
    return int(year), month

STATES = {'built': 'Built', 'live': 'Live', 'building': 'Building', 'next': 'Next', 'blocked': 'Blocked', 'delivered': 'Delivered', 'in_progress': 'In progress', 'proposed': 'Proposed', 'unrecorded': 'Not previously recorded'}
SCOPES = {'documentation': 'Documentation', 'offline': 'Offline validation', 'target-runtime': 'Runtime evidence', 'target-service': 'Service evidence', 'owner-confirmation': 'Owner confirmed'}
HORIZONS = [('immediate', 'Immediate', 'Establish the evidence and execution boundary.'), ('q4', 'Q4 · Foundations', 'Make the first agent and incident journey repeatable.'), ('q1', 'Q1 · Operational value', 'Deliver useful investigations, then make the offering reusable.')]


def delivery_window(milestone, windows):
    actual = milestone['live_on'] if milestone['state'] == 'live' else milestone['built_on'] if milestone['state'] == 'built' else None
    if not actual:
        return milestone['window']
    month = actual[:7]
    quarter = f"{actual[:4]}-Q{(int(actual[5:7]) - 1) // 3 + 1}"
    for period in [month, quarter]:
        if period in windows:
            return period
    raise ValueError('Extend the calendar to cover the actual delivery date: ' + milestone['id'])


def e(value):
    return escape(str(value), quote=True)


def badge(state):
    return f'<span class="delivery-state state-{e(state)}"><span aria-hidden="true" class="state-mark"></span>{STATES[state]}</span>'


def evidence_links(items):
    parts = []
    for item in items:
        url = item['url']
        parsed = urlsplit(url)
        if parsed.scheme and parsed.scheme != 'https':
            raise ValueError('Evidence must use HTTPS or a relative documentation link')
        if not parsed.scheme and (parsed.netloc or url.startswith('/') or '..' in Path(url).parts):
            raise ValueError('Evidence link must stay within the documentation project')
        if not parsed.scheme and parsed.path.endswith('.md'):
            url = parsed._replace(path=parsed.path[:-3] + '.html').geturl()
        parts.append(f'<a href="{e(url)}">{e(item["label"])}</a><span class="evidence-scope">{SCOPES[item["scope"]]}</span>')
    return '<span class="evidence-links">' + ' '.join(parts) + '</span>'


def refs(ids, lookup, prefix=''):
    return ', '.join(f'<a href="{prefix}roadmap.html#delivery-{e(i.lower())}">{e(lookup[i]["title"])}</a>' for i in ids)


def validate_data():
    roadmap = yaml.safe_load((ROOT / 'delivery/roadmap.yml').read_text())
    updates = yaml.safe_load((ROOT / 'delivery/updates.yml').read_text())
    for data, schema in [(roadmap, 'schema.json'), (updates, 'updates-schema.json')]:
        jsonschema.Draft7Validator(json.loads((ROOT / 'delivery' / schema).read_text()), format_checker=jsonschema.FormatChecker()).validate(data)
    lookup = {m['id']: m for m in roadmap['milestones']}
    if len(lookup) != len(roadmap['milestones']):
        raise ValueError('Milestone IDs must be unique')
    seen = set()
    windows = {w['id']: w for w in roadmap['calendar']['windows']}
    if len(windows) != len(roadmap['calendar']['windows']) or list(windows) != sorted(windows, key=period_order):
        raise ValueError('Calendar months must be unique and ordered')
    categories = {'agents': {'coordination', 'specialists'}, 'tools': {'mcp', 'skills'}, 'governance': {'policy', 'evaluation', 'observability', 'sdlc'}}
    for m in roadmap['milestones']:
        if m['category'] not in categories[m['track']] or m['window'] not in windows:
            raise ValueError('Invalid calendar lane or month: ' + m['id'])
        if m.get('historical') and (m['historical']['period'] != m['window'] or m['horizon'] != 'history' or not any(e['scope'] == 'owner-confirmation' for e in m['evidence'])):
            raise ValueError('Historical entry needs a matching period and explicit owner confirmation: ' + m['id'])
        if m['built_on'] and m['live_on'] and m['built_on'] > m['live_on']:
            raise ValueError('Live date cannot precede built date: ' + m['id'])
        actual = m['live_on'] if m['state'] == 'live' else m['built_on'] if m['state'] == 'built' else None
        delivery_window(m, windows)
        if not re.fullmatch(r'[A-Z][A-Z0-9-]*', m['id']):
            raise ValueError('Milestone ID must be a stable uppercase identifier')
        if any(dep not in lookup or dep == m['id'] for dep in m['dependencies']):
            raise ValueError('Invalid milestone dependency: ' + m['id'])
    def visit(id, stack):
        if id in stack:
            raise ValueError('Dependency cycle: ' + id)
        for dependency in lookup[id]['dependencies']:
            visit(dependency, stack | {id})
    for id in lookup:
        visit(id, set())
    for field in ['focus', 'next']:
        for id in roadmap[field]['milestones']:
            if id not in lookup:
                raise ValueError('Unknown summary milestone: ' + id)
    for update in updates['updates']:
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', update['id']) or update['id'] in seen:
            raise ValueError('Update IDs must be unique safe slugs')
        seen.add(update['id'])
        period = update['period']
        if period['start'] and not period['start'] <= period['end'] <= update['published']:
            raise ValueError('Reporting dates must be ordered')
        for field in ['achievements', 'moved', 'unchanged']:
            for row in update[field]:
                if row['milestone'] not in lookup:
                    raise ValueError('Unknown update milestone: ' + row['milestone'])
    return roadmap, sorted(updates['updates'], key=lambda u: u['published'], reverse=True), lookup


def milestone_html(m, lookup):
    deps = refs(m['dependencies'], lookup) if m['dependencies'] else 'No preceding milestone.'
    proof = evidence_links(m['evidence']) if m['evidence'] else '<p class="evidence-pending">Acceptance evidence pending.</p>'
    gate = '' if not m['gate'] else f'<p class="calendar-gate"><strong>Decision owner:</strong> {e(m["gate"]["owner"])}<br>{e(m["gate"]["decision"])}</p>'
    actual = m['live_on'] if m['state'] == 'live' else m['built_on'] if m['state'] == 'built' else None
    date_line = f'<time class="calendar-date" datetime="{e(actual)}">{STATES[m["state"]]} {e(actual)}</time>' if actual else ''
    if m.get('historical'):
        date_line = f'<span class="calendar-date history-basis">Owner confirmed<br>{e(m["historical"]["period"])} · approximate placement</span>'
    return f'''<article class="delivery-milestone calendar-item" id="delivery-{e(m['id'].lower())}" data-state="{e(m['state'])}" data-track="{e(m['track'])}">
<div class="milestone-meta">{badge(m['state'])}<span class="milestone-id">{e(m['id'])}</span></div><h3>{e(m['title'])}</h3>{date_line}
<details><summary>Evidence and acceptance</summary><div class="milestone-detail"><p>{e(m['outcome'])}</p><p><strong>Accountable role</strong><br>{e(m['owner'])}</p>{proof}<strong>Done means</strong><ul>{''.join('<li>'+e(a)+'</li>' for a in m['acceptance'])}</ul><p><strong>Depends on</strong><br>{deps}</p>{gate}<p><strong>Next action</strong><br>{e(m['next_action'])}</p></div></details></article>'''


def calendar_html(roadmap, lookup):
    windows = roadmap['calendar']['windows']
    quarters = []
    for w in windows:
        if not quarters or quarters[-1][0] != w['quarter']:
            quarters.append([w['quarter'], 1])
        else:
            quarters[-1][1] += 1
    quarter_head = ''.join(f'<th colspan="{n}" scope="colgroup" data-quarter-head="{e(q.split()[0].lower())}">{e(q)}</th>' for q,n in quarters)
    month_head = ''.join(f'<th scope="col" data-quarter="{e(w["quarter"].split()[0].lower())}"><span>{e(w["label"])}</span></th>' for w in windows)
    rows = [('agents', None, 'Agents', 'Delivered agents and next evolution'), ('tools', 'mcp', 'Tools · MCP', 'Approved tool operations'), ('tools', 'skills', 'Tools · Skills', 'Reviewed reusable procedures'), ('governance', 'policy', 'Governance · Policy', 'Identity, isolation and controls'), ('governance', 'evaluation', 'Governance · Evaluation', 'Quality and release acceptance'), ('governance', 'observability', 'Governance · Observability', 'Telemetry and operational ownership'), ('governance', 'sdlc', 'Governance · SDLC', 'Documentation and delivery process')]
    body = ''
    for track, category, label, subtitle in rows:
        cells = ''
        for w in windows:
            cards = []
            for m in roadmap['milestones']:
                actual = m['live_on'] if m['state'] == 'live' else m['built_on'] if m['state'] == 'built' else None
                month = delivery_window(m, {window['id'] for window in windows})
                if month == w['id'] and m['track'] == track and (category is None or m['category'] == category):
                    cards.append(milestone_html(m, lookup))
            cells += f'<td data-quarter="{e(w["quarter"].split()[0].lower())}" data-month="{e(w["id"])}">'+''.join(cards)+'<span class="calendar-cell-empty">No outcome scheduled</span></td>'
        body += f'<tr data-track-row="{track}"><th scope="row" class="calendar-lane"><strong>{label}</strong><span>{subtitle}</span></th>{cells}</tr>'
    return f'<div class="calendar-scroll" style="--calendar-min-width:{154 + 180 * len(windows)}px" role="region" tabindex="0" aria-label="Delivery calendar. Scroll left to right from historical achievements to current and future work."><table class="delivery-calendar"><caption>Agents, tools and governance by delivery month</caption><thead><tr><th rowspan="2" scope="col" class="calendar-corner">Workstream</th>'+quarter_head+'</tr><tr>'+month_head+'</tr></thead><tbody>'+body+'</tbody></table></div>'


def render(roadmap, updates, lookup):
    latest = updates[0]
    built = sum(m['state'] == 'built' for m in roadmap['milestones'])
    live = sum(m['state'] == 'live' for m in roadmap['milestones'])
    owner_confirmed = sum(bool(m.get('historical')) for m in roadmap['milestones'])
    building = sum(m['state'] == 'building' for m in roadmap['milestones'])
    go_live = f'{live} live with service acceptance' if live else 'Go-live dates awaiting record'
    quarter_buttons = ''.join(f'<button type="button" data-quarter-filter="{q.lower()}" aria-pressed="false">{q}</button>' for q in dict.fromkeys(w['quarter'].split()[0] for w in roadmap['calendar']['windows']))
    summary = f'''<div class="delivery-intro"><p class="delivery-lead">Delivered capabilities, active work and the next evolution of AI-enabled workflows.</p><p>{e(roadmap['calendar']['note'])}</p><div class="delivery-review"><span>Reviewed {e(roadmap['reviewed_on'])}</span><a href="achievements.html">Fortnightly achievements</a><a href="fortnightly-updates.html">Update this calendar</a></div></div>
<div class="calendar-status-line"><span><strong>{built} built</strong> · {owner_confirmed} owner-confirmed historical outcomes</span><span><strong>{building} building</strong></span><span>{go_live}</span></div>'''
    controls = '''<div class="delivery-controls" hidden><fieldset><legend>Calendar periods</legend><button type="button" data-quarter-filter="all" aria-pressed="true">All periods</button>__QUARTER_BUTTONS__</fieldset><div class="calendar-select"><label for="delivery-track">Workstream</label><select id="delivery-track"><option value="all">All workstreams</option><option value="agents">Agents</option><option value="tools">Tools and skills</option><option value="governance">Governance</option></select></div><div class="calendar-select"><label for="delivery-status">Status</label><select id="delivery-status"><option value="all">All statuses</option><option value="built">Built</option><option value="live">Live</option><option value="building">Building</option><option value="next">Next</option><option value="blocked">Blocked</option></select></div></div><div class="calendar-toolbar"><p class="delivery-filter-result" role="status" aria-live="polite"></p><div class="calendar-navigation" hidden><button type="button" data-scroll="-1" aria-label="Earlier months">Earlier</button><button type="button" data-scroll="1" aria-label="Later months">Later</button></div></div><p class="delivery-empty" hidden>No outcomes match these filters. Choose all months or another status.</p>'''
    controls = controls.replace('__QUARTER_BUTTONS__', quarter_buttons)
    legend = '<p class="calendar-legend">'+ ' '.join(badge(state) for state in ['built','live','building','next','blocked']) + '</p>'
    roadmap_md = '# '+roadmap['title']+'\n\n'+summary+'\n\n'+controls+legend+calendar_html(roadmap, lookup)+'\n\n## Current focus and next outcome\n\n'+roadmap['focus']['detail']+'\n\n**Next:** '+roadmap['next']['detail']+'\n\n## Keep delivery evidence with the documentation\n\nUpdate the maintained sources in the same commit when a milestone changes. Historical achievements retain their owner-confirmation basis and approximate quarter; current built/live states require the appropriate dated receipts. [Agent update instructions](fortnightly-updates.md) · [Achievements archive](achievements.md) · [North Star](direction.md) · [Acceptance evidence](evidence.md)\n'
    archive = '# What the pod has achieved\n\nA growing record of accepted outcomes, practical value and the next delivery. Each published update retains its original evidence scope.\n\n'
    archive += f'<div class="archive-feature"><span class="archive-date">{e(latest["period"]["label"])} · {e(latest["published"])}</span><h2>{e(latest["title"])}</h2><p>{e(latest["summary"])}</p><a class="primary-action" href="updates/{e(latest["id"])}.html">Read the complete update</a></div>\n\n'
    archive += '## Delivery record\n\n<div class="update-ledger">'+''.join(f'<article><time datetime="{e(u["published"])}">{e(u["published"])}</time><div><h3><a href="updates/{e(u["id"])}.html">{e(u["title"])}</a></h3><p>{e(u["summary"])}</p><span>{len(u["achievements"])} evidenced outcomes · {len(u["moved"])} state changes</span></div></article>' for u in updates)+'</div>\n\n[Add the next fortnightly update](fortnightly-updates.md) · [See the roadmap](roadmap.md)\n'
    outputs = {'docs/roadmap.md':roadmap_md, 'docs/achievements.md':archive}
    for u in updates:
        # Individual snapshots use normal MkDocs Markdown for reliable search and printing.
        lines = [f'# {u["title"]}', '', f'**{u["period"]["label"]} · Published {u["published"]}**', '', u['summary'], '', f'**Review:** {u["reviewer"]}', '', '## Achieved', '']
        for a in u['achievements']:
            links = ' · '.join(f'[{x["label"]}](../{x["url"]}) — {SCOPES[x["scope"]]}' if not urlsplit(x['url']).scheme else f'[{x["label"]}]({x["url"]}) — {SCOPES[x["scope"]]}' for x in a['evidence'])
            lines += [f'### {lookup[a["milestone"]]["title"]}', '', a['outcome'], '', '**Why it matters:** '+a['why_it_matters'], '', links, '']
        if not u['achievements']:
            lines += ['No newly accepted outcome in this reporting period. The update records progress, decisions and the next outcome below.', '']
        lines += ['## What moved', '', '| Outcome | Change | Why |', '| --- | --- | --- |']
        lines += [f'| {lookup[x["milestone"]]["title"]} | {STATES[x["from"]]} → {STATES[x["to"]]} | {x["reason"]} |' for x in u['moved']]
        if not u['moved']:
            lines += ['| No state change | Unchanged | No accepted state transition in this period. |']
        lines += ['', '## Unchanged and why', '']+[f'- **{lookup[x["milestone"]]["title"]}:** {x["reason"]}' for x in u['unchanged']]
        lines += ['', '## Next outcomes', '']+['- '+x for x in u['next']]
        lines += ['', '## Decisions needed', '']+[f'- **{x["owner"]}:** {x["decision"]}' for x in u['decisions']]
        lines += ['', '## Evidence scope', '', u['scope_note'], '', '[Back to achievements](../achievements.md) · [Delivery roadmap](../roadmap.md)', '']
        outputs['docs/updates/'+u['id']+'.md'] = '\n'.join(lines)
    return outputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    roadmap, updates, lookup = validate_data()
    outputs = render(roadmap, updates, lookup)
    stale = []
    for name, content in outputs.items():
        path = ROOT / name
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    if stale:
        sys.exit('Stale delivery pages: ' + ', '.join(stale))
    print(f'DELIVERY_{"FRESH" if args.check else "RENDERED"}: {len(roadmap["milestones"])} outcomes, {len(updates)} published updates')


if __name__ == '__main__':
    main()
