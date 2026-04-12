#!/usr/bin/env python3
"""Fetch upcoming CorkSec events from Meetup and write to data/upcoming.json."""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MEETUP_URL = "https://www.meetup.com/corksec/events/"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "upcoming.json"


def fetch_page(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_apollo_state(html):
    """Extract the __APOLLO_STATE__ JSON object from the page HTML.

    Meetup embeds data inside a __NEXT_DATA__ script tag, with
    __APOLLO_STATE__ nested at props.pageProps.__APOLLO_STATE__.
    """
    # Look for __NEXT_DATA__ (current Meetup format)
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if match:
        next_data = json.loads(match.group(1))
        apollo = (
            next_data.get("props", {})
            .get("pageProps", {})
            .get("__APOLLO_STATE__")
        )
        if apollo:
            return apollo

    # Fallback: try legacy window.__APOLLO_STATE__ patterns
    pattern = r'window\.__APOLLO_STATE__\s*=\s*JSON\.parse\("(.+?)"\);'
    match = re.search(pattern, html)
    if match:
        raw = match.group(1)
        raw = raw.replace('\\"', '"')
        raw = raw.replace("\\\\", "\\")
        raw = raw.replace("\\/", "/")
        raw = raw.replace("\\n", "\n")
        raw = raw.replace("\\t", "\t")
        return json.loads(raw)

    pattern2 = r'window\.__APOLLO_STATE__\s*=\s*({.+?});\s*</script>'
    match2 = re.search(pattern2, html, re.DOTALL)
    if match2:
        return json.loads(match2.group(1))

    return None


def parse_events(apollo_state):
    """Parse event entries from the Apollo state object."""
    events = []

    for key, value in apollo_state.items():
        if not key.startswith("Event:"):
            continue
        if not isinstance(value, dict):
            continue

        title = value.get("title", "")
        event_url = value.get("eventUrl", "")
        description = value.get("description", "")
        venue_ref = value.get("venue")

        # Parse date/time
        date_str = value.get("dateTime", "")
        date_obj = None
        event_date = ""
        event_time = ""
        if date_str:
            try:
                date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                event_date = date_obj.strftime("%Y-%m-%d")
                event_time = date_obj.strftime("%H:%M")
            except (ValueError, AttributeError):
                pass

        # Resolve venue
        venue_name = ""
        if isinstance(venue_ref, dict) and "__ref" in venue_ref:
            venue_data = apollo_state.get(venue_ref["__ref"], {})
            parts = [
                venue_data.get("name", ""),
                venue_data.get("address", ""),
                venue_data.get("city", ""),
            ]
            venue_name = ", ".join(p for p in parts if p)
        elif isinstance(venue_ref, dict):
            parts = [
                venue_ref.get("name", ""),
                venue_ref.get("address", ""),
                venue_ref.get("city", ""),
            ]
            venue_name = ", ".join(p for p in parts if p)

        # Extract talks from description
        talks = parse_talks_from_description(description)

        # Clean description: take first paragraph or truncate
        clean_desc = ""
        if description:
            # Strip HTML tags
            clean_desc = re.sub(r"<[^>]+>", "", description)
            # Take first meaningful paragraph
            paragraphs = [p.strip() for p in clean_desc.split("\n\n") if p.strip()]
            if paragraphs:
                clean_desc = paragraphs[0]
            if len(clean_desc) > 300:
                clean_desc = clean_desc[:297] + "..."

        event = {
            "title": title,
            "date": event_date,
            "time": event_time,
            "description": clean_desc,
            "venue": venue_name,
            "talks": talks,
            "meetupUrl": event_url,
        }
        events.append(event)

    # Sort by date ascending
    events.sort(key=lambda e: e.get("date", ""))

    # Only keep upcoming events (today or future)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    events = [e for e in events if e.get("date", "") >= today]

    return events


def parse_talks_from_description(description):
    """Extract individual talk titles and speakers from event description."""
    talks = []
    if not description:
        return talks

    # Strip HTML tags for parsing
    text = re.sub(r"<[^>]+>", "\n", description)

    # Look for patterns like "TALK 1: Title by Speaker" or "Talk: Title - Speaker"
    talk_pattern = re.compile(
        r"TALK\s*\d*\s*[:\-]\s*(.+?)(?:\s+[-\u2013\u2014]\s*by\s+|\s+by\s+)(.+?)$",
        re.IGNORECASE | re.MULTILINE,
    )
    for match in talk_pattern.finditer(text):
        title = match.group(1).strip().rstrip(" -\u2013\u2014").strip("*")
        speaker = match.group(2).strip().rstrip(".").strip("*")
        if title and speaker:
            talks.append({"title": title, "speaker": speaker})

    return talks


def main():
    print(f"Fetching {MEETUP_URL} ...")
    try:
        html = fetch_page(MEETUP_URL)
    except Exception as e:
        print(f"Error fetching page: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Page fetched ({len(html)} bytes). Extracting Apollo state...")
    apollo_state = extract_apollo_state(html)
    if not apollo_state:
        print("Warning: Could not extract __APOLLO_STATE__ from page.", file=sys.stderr)
        print("The page may have changed its data format.", file=sys.stderr)
        print("Writing empty events list.")
        events = []
    else:
        print(f"Apollo state has {len(apollo_state)} keys.")
        events = parse_events(apollo_state)
        print(f"Found {len(events)} upcoming event(s).")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
