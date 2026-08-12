#!/usr/bin/env python3
"""
Check Micro's /good and /bad endpoints to validate tracking implementation.
"""

import argparse
import requests
import json
import sys


def check_endpoint(port, endpoint):
    """Query a Micro endpoint and return results."""
    url = f"http://localhost:{port}/micro/{endpoint}"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"

        try:
            data = response.json()
            return data, None
        except ValueError:
            return None, "Response is not JSON"

    except requests.exceptions.RequestException as e:
        return None, str(e)


def format_good_event(event, index):
    """Format a good event for display."""
    output = [f"\n--- Event {index} ---"]

    if isinstance(event, dict):
        # Extract key fields
        event_data = event.get("event", {})
        event_type = event_data.get("event", "unknown")
        app_id = event_data.get("app_id", "N/A")
        schema = event.get("schema")
        contexts = event.get("contexts", [])

        output.append(f"Type: {event_type}")
        output.append(f"App ID: {app_id}")

        if schema:
            output.append(f"Schema: {schema}")

        if contexts:
            output.append(f"Contexts: {len(contexts)} attached")
            for ctx in contexts:
                if isinstance(ctx, dict) and "schema" in ctx:
                    output.append(f"  - {ctx['schema']}")

    return "\n".join(output)


def format_bad_event(event, index):
    """Format a bad event with errors for display."""
    output = [f"\n--- Bad Event {index} ---"]

    if isinstance(event, dict):
        errors = event.get("errors", [])
        timestamp = event.get("timestamp", "N/A")

        output.append(f"Timestamp: {timestamp}")
        output.append(f"Errors: {len(errors)}")

        for i, error in enumerate(errors, 1):
            if isinstance(error, dict):
                level = error.get("level", "unknown")
                message = error.get("message", "No message")
                output.append(f"\n  Error {i} [{level}]:")
                output.append(f"    {message}")
            else:
                output.append(f"\n  Error {i}: {error}")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Check Snowplow Micro good and bad events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port 9090
  %(prog)s --port 9090 --show-details
  %(prog)s --port 9090 --limit 5
        """
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port that Micro is listening on (default: 9090)"
    )

    parser.add_argument(
        "--show-details",
        action="store_true",
        help="Show full event details instead of summaries"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of events to display"
    )

    args = parser.parse_args()

    print(f"Checking Snowplow Micro on port {args.port}...\n")

    # Check good events
    print("=" * 60)
    print("GOOD EVENTS (Validated Successfully)")
    print("=" * 60)

    good_events, error = check_endpoint(args.port, "good")

    if error:
        print(f"✗ Error fetching good events: {error}")
        good_count = 0
    elif not good_events:
        print("No good events found")
        good_count = 0
    else:
        good_count = len(good_events)
        print(f"✓ Found {good_count} good event(s)")

        display_events = good_events[:args.limit] if args.limit else good_events

        if args.show_details:
            print(json.dumps(display_events, indent=2))
        else:
            for i, event in enumerate(display_events, 1):
                print(format_good_event(event, i))

        if args.limit and len(good_events) > args.limit:
            print(f"\n... and {len(good_events) - args.limit} more")

    # Check bad events
    print("\n")
    print("=" * 60)
    print("BAD EVENTS (Validation Failed)")
    print("=" * 60)

    bad_events, error = check_endpoint(args.port, "bad")

    if error:
        print(f"✗ Error fetching bad events: {error}")
        bad_count = 0
    elif not bad_events:
        print("No bad events found")
        bad_count = 0
    else:
        bad_count = len(bad_events)
        print(f"✗ Found {bad_count} bad event(s)")

        display_events = bad_events[:args.limit] if args.limit else bad_events

        if args.show_details:
            print(json.dumps(display_events, indent=2))
        else:
            for i, event in enumerate(display_events, 1):
                print(format_bad_event(event, i))

        if args.limit and len(bad_events) > args.limit:
            print(f"\n... and {len(bad_events) - args.limit} more")

    # Summary
    print("\n")
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Good events: {good_count}")
    print(f"Bad events: {bad_count}")

    if bad_count > 0:
        print("\n⚠️  Some events failed validation. Check error messages above.")
        print("Common causes:")
        print("  - Schema not found in Iglu registry")
        print("  - Missing required fields")
        print("  - Type mismatches")
        print("  - Additional properties not allowed")
        print("\nSee reference/validation_errors.md for detailed troubleshooting.")
    elif good_count > 0:
        print("\n✓ All events validated successfully!")
        print("Next steps:")
        print("  1. Deploy schemas to DEV environment")
        print("  2. Update tracker to point to DEV collector")
        print("  3. Test in DEV pipeline")
    elif good_count == 0 and bad_count == 0:
        print("\n⚠️  No events found in Micro.")
        print("Possible causes:")
        print("  - Tracker not sending to Micro endpoint")
        print("  - Application hasn't triggered any events yet")
        print("  - Network connectivity issues")
        print("\nSee troubleshooting/implementation_issues.md for help.")

    # Exit with error if bad events exist
    sys.exit(1 if bad_count > 0 else 0)


if __name__ == "__main__":
    main()
