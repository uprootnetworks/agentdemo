#!/usr/bin/env python3
"""Small sample-log analyzer and text-only setup-note reader."""

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

PROFILE_URL = "https://uprootnetworks.com/wp-content/uploads/2026/10/setup-profile.txt"
MAX_BYTES = 16_384
SAMPLE = Path(__file__).resolve().parent / "samples" / "connections.json"


class NoRedirects(urllib.request.HTTPRedirectHandler):
    """Keep the setup request at the fixed, reviewed HTTPS destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_notes():
    request = urllib.request.Request(
        PROFILE_URL,
        headers={"Accept": "text/plain", "User-Agent": "NetworkTriage-Demo/1.0"},
    )
    opener = urllib.request.build_opener(NoRedirects())
    with opener.open(request, timeout=10) as response:
        if response.headers.get_content_type() != "text/plain":
            raise ValueError("Setup notes must be served as text/plain.")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Setup notes exceed the 16 KiB limit.")
    notes = data.decode("utf-8")
    if not notes.strip():
        raise ValueError("Setup notes are empty.")
    # Preserve text, not terminal escape sequences or invisible control characters.
    return "".join(c if c.isprintable() or c in "\n\t" else "?" for c in notes)


def summarize(records):
    if not isinstance(records, list) or not records:
        raise ValueError("Sample log must be a nonempty list.")
    totals = Counter()
    failures = Counter()
    errors = Counter()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each sample entry must be an object.")
        destination = record.get("destination")
        status = record.get("status")
        if (
            not isinstance(destination, str)
            or not destination
            or len(destination) > 253
            or any(not c.isprintable() for c in destination)
            or status not in ("ok", "dns_timeout", "tls_error", "connection_timeout")
        ):
            raise ValueError("Invalid destination or status in sample log.")
        totals[destination] += 1
        if status != "ok":
            failures[destination] += 1
            errors[status] += 1
    lines = ["Network Triage — sample report", "Synthetic logs; no live hosts were contacted.", ""]
    for destination in sorted(totals, key=lambda name: (-failures[name], name)):
        failed, total = failures[destination], totals[destination]
        lines.append(f"{destination}: {failed}/{total} failed ({failed / total:.0%})")
    lines.extend(["", "Error totals:"])
    lines.extend(f"  {error}: {count}" for error, count in sorted(errors.items()))
    lines.extend([
        "", "Suggested next steps:",
        "  Check resolver health for destinations with DNS timeouts.",
        "  Check certificate validity and trust for destinations with TLS errors.",
        "  Compare against real monitoring data before taking action.",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "report"))
    args = parser.parse_args()
    try:
        if args.command == "setup":
            print(f"Setup notes from {PROFILE_URL}\n")
            print(fetch_notes())
        else:
            with SAMPLE.open("rb") as sample:
                data = sample.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("Sample log exceeds the 16 KiB limit.")
            print(summarize(json.loads(data)))
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"Network Triage: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
