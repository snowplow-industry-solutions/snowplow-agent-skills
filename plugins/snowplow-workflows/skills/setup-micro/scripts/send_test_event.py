#!/usr/bin/env python3
"""
Sends a test Snowplow event to Micro for end-to-end validation.
"""

import argparse
import requests
import json
import sys
import uuid
from datetime import datetime


def send_page_view(port):
    """Send a simple page view event."""
    url = f"http://localhost:{port}/i"

    params = {
        "e": "pv",  # Event type: page view
        "url": "http://example.com/test",
        "page": "Test Page",
        "tv": "py-test-0.1",  # Tracker version
        "tna": "test-tracker",  # Tracker namespace
        "aid": "test-app",  # App ID
        "p": "web",  # Platform
        "eid": str(uuid.uuid4()),  # Event ID
        "dtm": str(int(datetime.now().timestamp() * 1000)),  # Timestamp
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        return response.status_code == 200, "page_view", params
    except requests.exceptions.RequestException as e:
        return False, "page_view", str(e)


def send_structured_event(port):
    """Send a structured event."""
    url = f"http://localhost:{port}/i"

    params = {
        "e": "se",  # Event type: structured event
        "se_ca": "test_category",  # Category
        "se_ac": "test_action",  # Action
        "se_la": "test_label",  # Label
        "se_pr": "test_property",  # Property
        "se_va": "100",  # Value
        "tv": "py-test-0.1",
        "tna": "test-tracker",
        "aid": "test-app",
        "p": "web",
        "eid": str(uuid.uuid4()),
        "dtm": str(int(datetime.now().timestamp() * 1000)),
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        return response.status_code == 200, "structured_event", params
    except requests.exceptions.RequestException as e:
        return False, "structured_event", str(e)


def send_self_describing_event(port):
    """Send a self-describing event with schema."""
    url = f"http://localhost:{port}/com.snowplowanalytics.snowplow/tp2"

    # Self-describing event with minimal test schema
    event = {
        "schema": "iglu:com.snowplowanalytics.snowplow/unstruct_event/jsonschema/1-0-0",
        "data": {
            "schema": "iglu:com.example/test_event/jsonschema/1-0-0",
            "data": {
                "test_field": "test_value"
            }
        }
    }

    payload = {
        "schema": "iglu:com.snowplowanalytics.snowplow/payload_data/jsonschema/1-0-4",
        "data": [{
            "e": "ue",  # Unstructured event
            "ue_pr": json.dumps(event),
            "tv": "py-test-0.1",
            "tna": "test-tracker",
            "aid": "test-app",
            "p": "web",
            "eid": str(uuid.uuid4()),
            "dtm": str(int(datetime.now().timestamp() * 1000)),
        }]
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        return response.status_code == 200, "self_describing", payload
    except requests.exceptions.RequestException as e:
        return False, "self_describing", str(e)


def main():
    parser = argparse.ArgumentParser(
        description="Send test events to Snowplow Micro",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port that Micro is listening on (default: 9090)"
    )

    parser.add_argument(
        "--event-type",
        type=str,
        choices=["page_view", "struct", "self_describing", "all"],
        default="page_view",
        help="Type of event to send (default: page_view)"
    )

    args = parser.parse_args()

    print(f"Sending test event(s) to Snowplow Micro on port {args.port}...\n")

    event_types = {
        "page_view": send_page_view,
        "struct": send_structured_event,
        "self_describing": send_self_describing_event,
    }

    if args.event_type == "all":
        types_to_send = event_types.keys()
    else:
        types_to_send = [args.event_type]

    results = []
    for event_type in types_to_send:
        send_func = event_types[event_type]
        success, name, data = send_func(args.port)
        results.append((success, name, data))

        if success:
            print(f"[OK] Sent {name} event")
        else:
            print(f"[ERROR] Failed to send {name} event: {data}")

    # Check results
    print(f"\nNext steps:")
    print(f"  1. Check good events: curl http://localhost:{args.port}/micro/good")
    print(f"  2. Or use: python scripts/check_good_bad.py --port {args.port}")

    if all(r[0] for r in results):
        sys.exit(0)
    else:
        print("\n[ERROR] Some events failed to send")
        sys.exit(1)


if __name__ == "__main__":
    main()
