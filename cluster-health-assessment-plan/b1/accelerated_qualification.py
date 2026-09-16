#!/usr/bin/env python3
"""Exercise 20 scheduled report slots without claiming that real soak time elapsed."""

import json
from datetime import date

from calibration import expected_slots


def replay(start=date(2026, 10, 19), end=date(2026, 10, 30)):
    slots = list(expected_slots(start, end))
    names = [name for name, _ in slots]
    offsets = sorted({scheduled.strftime("%z") for _, scheduled in slots})
    weekdays = {scheduled.date().isoformat() for _, scheduled in slots}
    if len(slots) != 20 or len(set(names)) != 20 or len(weekdays) != 10:
        raise RuntimeError("accelerated slot qualification failed")
    if offsets != ["+0000", "+0100"]:
        raise RuntimeError("DST boundary was not exercised")
    return {
        "result": "pass",
        "mode": "accelerated_synthetic_replay",
        "slot_count": len(slots),
        "working_day_count": len(weekdays),
        "spans_weekend": True,
        "spans_dst_change": True,
        "utc_offsets": offsets,
        "unique_slot_ids": len(set(names)),
        "substitutes_for_real_elapsed_soak": False,
        "qualified": ["schedule identity", "timezone handling", "twenty-slot report shape"],
        "not_qualified": ["real reliability", "real false-positive rate", "SRE acceptance"],
    }


if __name__ == "__main__":
    print(json.dumps(replay(), sort_keys=True))
