#!/usr/bin/env python3
"""
Analyze failed Snowplow events from either Snowplow Micro (local) or a JSON
file produced by any other source (MCP export, Console download, warehouse
query, single bad-row pasted into a file, etc.). Categorizes errors and
summarizes the most common failures.
"""

import argparse
import json
import sys
from collections import defaultdict


def fetch_from_micro(port):
    """Fetch failed events from Snowplow Micro's /micro/bad endpoint."""
    import requests

    url = f"http://localhost:{port}/micro/bad"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None, f"HTTP {response.status_code} from {url}"
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def load_from_file(path):
    """Load failed events from a JSON file.

    Accepts either:
      - a JSON array of failed-event objects: [{...}, {...}]
      - a single failed-event object: {...}  (will be wrapped to [...])
    """
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, f"Could not read {path}: {e}"

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return None, f"Expected JSON array or object in {path}, got {type(data).__name__}"

    return data, None


def categorize_error(error_message):
    """Categorize error by type."""
    message_lower = error_message.lower()

    # Schema resolution errors
    if 'schema' in message_lower and ('not found' in message_lower or 'resolution' in message_lower):
        return 'schema_resolution'

    if 'timeout' in message_lower and 'resolv' in message_lower:
        return 'schema_resolution'

    # Schema validation errors
    if 'missing required' in message_lower or 'required propert' in message_lower:
        return 'schema_validation'

    if 'additional propert' in message_lower or 'not allowed' in message_lower:
        return 'schema_validation'

    if 'type' in message_lower and 'does not match' in message_lower:
        return 'schema_validation'

    if 'enum' in message_lower or 'pattern' in message_lower:
        return 'schema_validation'

    if 'validation' in message_lower:
        return 'schema_validation'

    # Enrichment errors
    if 'enrichment' in message_lower:
        return 'enrichment'

    # Malformed events
    if 'parse' in message_lower or 'invalid json' in message_lower:
        return 'malformed'

    if 'corrupt' in message_lower or 'malformed' in message_lower:
        return 'malformed'

    return 'other'


def extract_schema_uri(error_message):
    """Extract Iglu URI from error message if present."""
    import re
    pattern = r'iglu:[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/jsonschema/\d+-\d+-\d+'
    match = re.search(pattern, error_message)
    return match.group(0) if match else None


def iter_error_messages(event):
    """Yield error message strings from a single failed-event object.

    Tolerates the two common shapes:
      - Micro / file: {"errors": [{"message": "..."} | "..."]}
      - Bad-row JSON: {"data": {"failure": {"messages": [{"message": "..."}]}}}
    """
    errors = event.get('errors')
    if errors:
        for err in errors:
            if isinstance(err, dict):
                yield err.get('message', 'Unknown error')
            else:
                yield str(err)
        return

    # Bad-row shape from real pipelines
    failure = (event.get('data') or {}).get('failure') or event.get('failure')
    if isinstance(failure, dict):
        for msg in failure.get('messages', []):
            if isinstance(msg, dict):
                yield msg.get('message') or msg.get('field') or json.dumps(msg)
            else:
                yield str(msg)


def analyze_events(events):
    """Analyze and categorize failed events."""
    if not events:
        return {
            'total': 0,
            'by_category': {},
            'by_error': {},
            'schemas': set(),
        }

    categories = defaultdict(int)
    error_messages = defaultdict(int)
    schemas = set()

    for event in events:
        for message in iter_error_messages(event):
            categories[categorize_error(message)] += 1
            error_messages[message] += 1
            schema = extract_schema_uri(message)
            if schema:
                schemas.add(schema)

    return {
        'total': len(events),
        'by_category': dict(categories),
        'by_error': dict(error_messages),
        'schemas': schemas,
    }


def print_analysis(analysis):
    """Print analysis results."""
    print("=" * 70)
    print("FAILED EVENTS ANALYSIS")
    print("=" * 70)

    print(f"\nTotal failed events: {analysis['total']}")

    if analysis['total'] == 0:
        print("\nNo failed events found.")
        return

    print("\n" + "-" * 70)
    print("BY ERROR CATEGORY")
    print("-" * 70)

    category_labels = {
        'schema_resolution': 'Schema Resolution Errors (schema not found, registry timeout)',
        'schema_validation': 'Schema Validation Errors (missing fields, type mismatches, etc.)',
        'enrichment': 'Enrichment Errors',
        'malformed': 'Malformed Events (invalid JSON, corrupt payload)',
        'other': 'Other/Uncategorized Errors',
    }

    ref_docs = {
        'schema_resolution': 'reference/schema_resolution_errors.md',
        'schema_validation': 'reference/schema_validation_errors.md',
        'enrichment': 'reference/enrichment_errors.md',
        'malformed': 'reference/malformed_events.md',
    }

    for category in ['schema_resolution', 'schema_validation', 'enrichment', 'malformed', 'other']:
        count = analysis['by_category'].get(category, 0)
        if count > 0:
            label = category_labels.get(category, category)
            percentage = (count / analysis['total']) * 100
            print(f"\n{category.upper()}: {count} events ({percentage:.1f}%)")
            print(f"  {label}")
            if category in ref_docs:
                print(f"  -> See {ref_docs[category]} for detailed guidance")

    if analysis['schemas']:
        print("\n" + "-" * 70)
        print("SCHEMAS INVOLVED")
        print("-" * 70)
        for schema in sorted(analysis['schemas']):
            print(f"  - {schema}")

    print("\n" + "-" * 70)
    print("MOST COMMON ERROR MESSAGES")
    print("-" * 70)

    sorted_errors = sorted(
        analysis['by_error'].items(),
        key=lambda x: x[1],
        reverse=True,
    )

    for i, (message, count) in enumerate(sorted_errors[:5], 1):
        percentage = (count / analysis['total']) * 100
        print(f"\n{i}. Count: {count} ({percentage:.1f}%)")
        display_message = message if len(message) < 100 else message[:97] + '...'
        print(f"   Message: {display_message}")

    if len(sorted_errors) > 5:
        print(f"\n... and {len(sorted_errors) - 5} more error types")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze failed Snowplow events from Micro or a JSON file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pull from local Snowplow Micro
  %(prog)s --source micro --port 9090

  # Analyze a JSON file of failed events (from MCP, Console, warehouse, paste)
  %(prog)s --source file --input failed_events.json

  # JSON output
  %(prog)s --source micro --format json
        """,
    )

    parser.add_argument(
        "--source",
        choices=["micro", "file"],
        required=True,
        help="Where to read failed events from: 'micro' (HTTP fetch from Snowplow Micro) or 'file' (JSON file from any source).",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port that Micro is listening on (default: 9090). Used only with --source micro.",
    )

    parser.add_argument(
        "--input",
        "-i",
        help="Path to a JSON file containing failed events. Used only with --source file.",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Save analysis to JSON file",
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

    if args.source == "micro":
        print(f"Fetching failed events from Micro (port {args.port})...")
        events, error = fetch_from_micro(args.port)
        if error:
            print(f"Error: {error}")
            print("\nTroubleshooting:")
            print("  1. Check if Micro is running: docker ps | grep micro")
            print("  2. Verify --port matches Micro's listening port")
            sys.exit(1)
    else:
        if not args.input:
            parser.error("--input is required when --source file")
        print(f"Loading failed events from {args.input}...")
        events, error = load_from_file(args.input)
        if error:
            print(f"Error: {error}")
            sys.exit(1)

    analysis = analyze_events(events)

    if args.format == "json" or args.output:
        analysis_json = {
            **analysis,
            'schemas': sorted(analysis['schemas']),
        }

        if args.format == "json":
            print(json.dumps(analysis_json, indent=2))

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(analysis_json, f, indent=2)
            print(f"\nAnalysis saved to {args.output}")
    else:
        print_analysis(analysis)

    if analysis['total'] > 0:
        print("\n" + "=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("\n1. Review the error categories above")
        print("2. Read the relevant reference documentation")
        print("3. Follow the diagnostic workflow in debug-failed-events SKILL.md")
        print("4. Apply fixes and re-test (re-emit event, then re-run this script)")

    sys.exit(1 if analysis['total'] > 0 else 0)


if __name__ == "__main__":
    main()
