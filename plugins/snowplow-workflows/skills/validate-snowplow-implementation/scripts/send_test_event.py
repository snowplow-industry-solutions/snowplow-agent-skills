#!/usr/bin/env python3
"""
Send a test event directly to Micro for quick validation testing.
Web/JavaScript tracker events only.
"""

import argparse
import requests
import json
import uuid
import sys
from datetime import datetime


def generate_page_view_event(app_id):
    """Generate a simple page_view event payload."""
    event_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    return {
        "e": "pv",  # page_view event
        "eid": event_id,
        "dtm": int(datetime.utcnow().timestamp() * 1000),
        "tv": "py-test-1.0",
        "p": "web",
        "aid": app_id,
        "url": "http://example.com/test",
        "page": "Test Page",
        "refr": "http://example.com"
    }


def generate_struct_event(app_id, category, action):
    """Generate a structured event payload."""
    event_id = str(uuid.uuid4())

    return {
        "e": "se",  # structured event
        "eid": event_id,
        "dtm": int(datetime.utcnow().timestamp() * 1000),
        "tv": "py-test-1.0",
        "p": "web",
        "aid": app_id,
        "se_ca": category,
        "se_ac": action,
        "url": "http://example.com/test"
    }


def send_event(port, payload):
    """Send event payload to Micro collector endpoint."""
    url = f"http://localhost:{port}/i"

    try:
        response = requests.get(url, params=payload, timeout=5)

        if response.status_code == 200:
            return True, "Event sent successfully"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.RequestException as e:
        return False, f"Error sending event: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description="Send a test event to Snowplow Micro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port 9090 --event page_view
  %(prog)s --port 9090 --event struct --category test --action click
  %(prog)s --port 9090 --event page_view --app-id my-test-app
        """
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port that Micro is listening on (default: 9090)"
    )

    parser.add_argument(
        "--event",
        choices=["page_view", "struct"],
        default="page_view",
        help="Type of event to send (default: page_view)"
    )

    parser.add_argument(
        "--app-id",
        type=str,
        default="test-app",
        help="Application ID to use (default: test-app)"
    )

    parser.add_argument(
        "--category",
        type=str,
        default="test",
        help="Event category (for struct events, default: test)"
    )

    parser.add_argument(
        "--action",
        type=str,
        default="test_action",
        help="Event action (for struct events, default: test_action)"
    )

    args = parser.parse_args()

    # Generate event payload
    if args.event == "page_view":
        print(f"Generating page_view event...")
        payload = generate_page_view_event(args.app_id)
    else:
        print(f"Generating structured event ({args.category}/{args.action})...")
        payload = generate_struct_event(args.app_id, args.category, args.action)

    print(f"Payload: {json.dumps(payload, indent=2)}\n")

    # Send event
    print(f"Sending to Micro on port {args.port}...")
    success, message = send_event(args.port, payload)

    if success:
        print(f"✓ {message}")
        print(f"\nCheck event status:")
        print(f"  python scripts/check_good_bad.py --port {args.port}")
        sys.exit(0)
    else:
        print(f"✗ {message}")
        print(f"\nTroubleshooting:")
        print(f"  1. Verify Micro is running: python scripts/check_micro_status.py --port {args.port}")
        print(f"  2. Check Micro logs: docker compose logs micro")
        sys.exit(1)


if __name__ == "__main__":
    main()
