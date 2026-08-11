#!/usr/bin/env python3
"""
Queries Micro's /good endpoint and formats the output.
"""

import argparse
import requests
import json
import sys


def check_endpoint(port, endpoint, filter_vendor=None):
    """Query a Micro endpoint and return formatted results."""
    url = f"http://localhost:{port}/micro/{endpoint}"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None, f"Status code {response.status_code}"

        try:
            events = response.json()

            if filter_vendor:
                events = [
                    e for e in events
                    if filter_vendor in json.dumps(e)
                ]

            return events, None
        except ValueError:
            return None, "Response is not JSON"

    except requests.exceptions.RequestException as e:
        return None, str(e)


def format_event_summary(event):
    """Extract key info from an event for display."""
    summary = {}

    # Try to extract common fields
    if isinstance(event, dict):
        summary["event_type"] = event.get("event", "unknown")
        summary["event_id"] = event.get("event_id", "N/A")

        # Look for schema info
        if "schema" in event:
            summary["schema"] = event["schema"]

        # Look for failure info (for bad events)
        if "errors" in event:
            summary["errors"] = event["errors"]

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Check Snowplow Micro good endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port that Micro is listening on (default: 9090)"
    )

    parser.add_argument(
        "--filter-vendor",
        type=str,
        help="Filter events to only those containing this vendor string"
    )

    parser.add_argument(
        "--format",
        choices=["summary", "full"],
        default="summary",
        help="Output format (default: summary)"
    )

    args = parser.parse_args()

    print(f"Checking Snowplow Micro endpoints on port {args.port}...\n")

    # Check good events
    print("=== GOOD EVENTS ===")
    good_events, error = check_endpoint(args.port, "good", args.filter_vendor)

    if error:
        print(f"[ERROR] {error}")
    elif not good_events:
        print("No good events found")
    else:
        print(f"Found {len(good_events)} good event(s)\n")

        if args.format == "full":
            print(json.dumps(good_events, indent=2))
        else:
            for i, event in enumerate(good_events, 1):
                summary = format_event_summary(event)
                print(f"{i}. {json.dumps(summary, indent=2)}")

    # Exit with error only if we couldn't fetch good events
    sys.exit(0 if good_events is not None else 1)


if __name__ == "__main__":
    main()
