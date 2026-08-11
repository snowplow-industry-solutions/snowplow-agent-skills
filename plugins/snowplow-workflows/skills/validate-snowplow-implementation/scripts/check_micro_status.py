#!/usr/bin/env python3
"""
Check if Snowplow Micro is running and accessible.
"""

import argparse
import requests
import sys


def check_micro_health(port):
    """Check if Micro is responding to health check."""
    url = f"http://localhost:{port}/micro/all"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return True, "Micro is running and accessible"
        else:
            return False, f"Micro returned status code {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, "Connection refused. Micro is not running or not accessible."

    except requests.exceptions.Timeout:
        return False, "Request timed out. Micro may be unresponsive."

    except requests.exceptions.RequestException as e:
        return False, f"Error connecting to Micro: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description="Check if Snowplow Micro is running and accessible",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port 9090
  %(prog)s --port 8080
        """
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port that Micro should be listening on (default: 9090)"
    )

    args = parser.parse_args()

    print(f"Checking Snowplow Micro on port {args.port}...")

    is_running, message = check_micro_health(args.port)

    if is_running:
        print(f"✓ {message}")
        print(f"\nMicro endpoints:")
        print(f"  - Good events: http://localhost:{args.port}/micro/good")
        print(f"  - Bad events:  http://localhost:{args.port}/micro/bad")
        print(f"  - All events:  http://localhost:{args.port}/micro/all")
        print(f"  - Reset:       POST http://localhost:{args.port}/micro/reset")
        sys.exit(0)
    else:
        print(f"✗ {message}")
        print(f"\nTroubleshooting:")
        print(f"  1. Check if Micro container is running: docker ps | grep micro")
        print(f"  2. Start Micro if not running: docker compose up -d")
        print(f"  3. Check logs: docker compose logs micro")
        print(f"  4. Verify port {args.port} is not blocked by firewall")
        sys.exit(1)


if __name__ == "__main__":
    main()
