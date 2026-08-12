#!/usr/bin/env python3
"""
Validates that Snowplow Micro is running and properly configured.
"""

import argparse
import requests
import sys
import time


def check_micro_health(port, max_retries=3, retry_delay=2):
    """Check if Micro is responding to HTTP requests."""
    url = f"http://localhost:{port}/micro/good"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return True, "Micro is responding"
            else:
                return False, f"Micro returned status code {response.status_code}"
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                print(f"  Attempt {attempt + 1}/{max_retries}: Connection failed, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                return False, "Cannot connect to Micro. Is it running?"
        except requests.exceptions.RequestException as e:
            return False, f"Request failed: {str(e)}"

    return False, "Max retries exceeded"


def check_endpoints(port):
    """Check that /good endpoint is accessible."""
    results = {}

    endpoint = "good"
    url = f"http://localhost:{port}/micro/{endpoint}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            try:
                data = response.json()
                results[endpoint] = {
                    "status": "ok",
                    "count": len(data) if isinstance(data, list) else 0
                }
            except ValueError:
                results[endpoint] = {
                    "status": "ok",
                    "count": 0,
                    "note": "Response is not JSON"
                }
        else:
            results[endpoint] = {
                "status": "error",
                "message": f"Status code {response.status_code}"
            }
    except requests.exceptions.RequestException as e:
        results[endpoint] = {
            "status": "error",
            "message": str(e)
        }

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Validate Snowplow Micro setup",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port that Micro is listening on (default: 9090)"
    )

    args = parser.parse_args()

    print(f"Validating Snowplow Micro on port {args.port}...\n")

    # Check basic health
    print("1. Checking Micro health...")
    healthy, message = check_micro_health(args.port)
    if healthy:
        print(f"   [OK] {message}")
    else:
        print(f"   [ERROR] {message}")
        print("\nTroubleshooting:")
        print("  - Ensure Docker is running: docker ps")
        print("  - Check Micro logs: docker logs snowplow-micro")
        print("  - Verify port is not in use: lsof -i :{args.port}")
        sys.exit(1)

    # Check endpoints
    print("\n2. Checking endpoints...")
    endpoints = check_endpoints(args.port)

    for endpoint, result in endpoints.items():
        if result["status"] == "ok":
            count = result.get("count", 0)
            print(f"   [OK] /{endpoint} endpoint accessible ({count} events)")
        else:
            print(f"   [ERROR] /{endpoint} endpoint error: {result['message']}")

    # Summary
    all_ok = healthy and all(r["status"] == "ok" for r in endpoints.values())

    if all_ok:
        print("\n[OK] Snowplow Micro is configured correctly!")
        print(f"\nEndpoints:")
        print(f"  - Good events: http://localhost:{args.port}/micro/good")
        print(f"  - Reset:       http://localhost:{args.port}/micro/reset (POST)")
        sys.exit(0)
    else:
        print("\n[ERROR] Validation failed. See troubleshooting/ directory for help.")
        sys.exit(1)


if __name__ == "__main__":
    main()
