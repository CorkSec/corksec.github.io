#!/usr/bin/env python3
"""Move past events from upcoming.json into past-events.json."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPCOMING = DATA_DIR / "upcoming.json"
PAST = DATA_DIR / "past-events.json"


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Archiving events that occurred before {today} ...")

    # Load upcoming events
    if not UPCOMING.exists():
        print("No upcoming.json found. Nothing to archive.")
        return

    upcoming = json.loads(UPCOMING.read_text())
    if not upcoming:
        print("No upcoming events. Nothing to archive.")
        return

    # Split into still-upcoming and already-past
    still_upcoming = []
    to_archive = []
    for event in upcoming:
        if event.get("date", "") < today:
            to_archive.append(event)
        else:
            still_upcoming.append(event)

    if not to_archive:
        print("No events to archive.")
        return

    print(f"Found {len(to_archive)} event(s) to archive.")

    # Load existing past events
    if PAST.exists():
        past = json.loads(PAST.read_text())
    else:
        past = []

    # Deduplicate: skip events already present in past-events.json (by date)
    existing_dates = {e.get("date") for e in past}
    new_entries = []
    for event in to_archive:
        if event["date"] in existing_dates:
            print(f"  Skipping {event['title']} ({event['date']}) - already archived.")
            continue

        # Convert to past-events schema (drop event-level description)
        entry = {
            "title": event.get("title", ""),
            "date": event.get("date", ""),
            "time": event.get("time", ""),
            "venue": event.get("venue", ""),
            "talks": event.get("talks", []),
            "meetupUrl": event.get("meetupUrl", ""),
        }
        new_entries.append(entry)
        print(f"  Archiving {entry['title']} ({entry['date']})")

    if not new_entries:
        print("All events already archived. No changes needed.")
        return

    # Prepend new entries (newest first), then existing past events
    new_entries.sort(key=lambda e: e["date"], reverse=True)
    past = new_entries + past

    # Write updated files
    PAST.write_text(json.dumps(past, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {PAST}")

    UPCOMING.write_text(json.dumps(still_upcoming, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {UPCOMING}")

    print(f"Done. Archived {len(new_entries)} event(s).")


if __name__ == "__main__":
    main()
