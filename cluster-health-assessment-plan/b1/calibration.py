#!/usr/bin/env python3
"""Audit expected weekday report slots from exported report ConfigMaps."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
SLOTS = ((time(7, 30), "morning"), (time(16, 30), "evening"))


def expected_slots(start: date, end: date):
    current = start
    while current <= end:
        if current.weekday() < 5:
            for slot_time, name in SLOTS:
                scheduled = datetime.combine(current, slot_time, LONDON)
                yield "{}-{}".format(current.strftime("%Y%m%d"), name), scheduled
        current += timedelta(days=1)


def reports_from_configmaps(document: dict) -> dict:
    reports = {}
    for item in document.get("items", []):
        raw = (item.get("data") or {}).get("report.json")
        if not raw:
            continue
        try:
            report = json.loads(raw)
        except ValueError:
            continue
        slot = report.get("report_slot", "")
        if slot and not slot.startswith("b1-smoke"):
            reports[slot] = report
    return reports


def audit(start: date, end: date, reports: dict, now: datetime):
    rows = []
    for slot, scheduled in expected_slots(start, end):
        report = reports.get(slot)
        if report:
            state = report.get("timing", "recorded")
        elif now > scheduled + timedelta(minutes=30):
            state = "missed"
        else:
            state = "pending"
        rows.append({
            "report_slot": slot,
            "scheduled_at": scheduled.isoformat(),
            "state": state,
            "snapshot_ref": (report or {}).get("snapshot_ref", ""),
            "score": (report or {}).get("display_score", ""),
            "coverage_complete": (report or {}).get("coverage", {}).get("complete", ""),
            "operator_label": "",
            "false_positive_rules": "",
            "notes": "",
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    document = json.load(sys.stdin)
    rows = audit(args.start, args.end, reports_from_configmaps(document), datetime.now(LONDON))
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys() if rows else [])
    if rows:
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
