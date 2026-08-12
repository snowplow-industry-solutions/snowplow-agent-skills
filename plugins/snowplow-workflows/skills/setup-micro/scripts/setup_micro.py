#!/usr/bin/env python3
"""
Generates docker-compose.yml for Snowplow Micro with optional schema and enrichment mounting.
"""

import argparse
import os
import sys
from pathlib import Path


def validate_schemas_path(schemas_path):
    """Validates that the schemas directory follows Iglu conventions."""
    if not os.path.exists(schemas_path):
        return False, f"Schemas path does not exist: {schemas_path}"

    if not os.path.isdir(schemas_path):
        return False, f"Schemas path is not a directory: {schemas_path}"

    # Check for typical Iglu structure (schemas/ directory with vendor subdirectories)
    # This is a basic check - deeper validation happens when Micro loads them
    has_content = any(os.scandir(schemas_path))
    if not has_content:
        return False, f"Schemas directory is empty: {schemas_path}"

    return True, "Schemas path looks valid"


def validate_enrichments_path(enrichments_path):
    """Validates that the enrichments directory contains valid config files."""
    if not os.path.exists(enrichments_path):
        return False, f"Enrichments path does not exist: {enrichments_path}"

    if not os.path.isdir(enrichments_path):
        return False, f"Enrichments path is not a directory: {enrichments_path}"

    # Check for JSON files
    json_files = list(Path(enrichments_path).glob("*.json"))
    if not json_files:
        return False, f"No .json enrichment config files found in: {enrichments_path}"

    return True, f"Found {len(json_files)} enrichment config file(s)"


def validate_iglu_registry_url(url):
    """Validates that the Iglu registry URL is properly formatted."""
    if not url.startswith(('http://', 'https://')):
        return False, "Iglu registry URL must start with http:// or https://"

    # Check if it looks like a valid URL
    if ' ' in url:
        return False, "Iglu registry URL contains spaces"

    return True, "Iglu registry URL looks valid"


def generate_docker_compose(port, schemas_path=None, enrichments_path=None,
                           iglu_registry_url=None, use_env_file=False):
    """Generates docker-compose.yml content based on requirements."""

    # Base configuration
    compose = f"""version: '3.8'

services:
  micro:
    image: snowplow/snowplow-micro:4.2.0
    container_name: snowplow-micro
    ports:
      - "{port}:{port}"
"""

    # Add volume mounts if needed
    if schemas_path or enrichments_path:
        compose += "    volumes:\n"

        if schemas_path:
            abs_schemas_path = os.path.abspath(schemas_path)
            compose += f"      - {abs_schemas_path}:/config/iglu-client-embedded/schemas\n"

        if enrichments_path:
            abs_enrichments_path = os.path.abspath(enrichments_path)
            compose += f"      - {abs_enrichments_path}:/config/enrichments\n"

    # Add env_file if using .env for credentials
    if use_env_file:
        compose += "    env_file:\n"
        compose += "      - .env\n"

    # Add environment variables for custom configuration
    compose += "    environment:\n"
    compose += f"      - MICRO_PORT={port}\n"

    if enrichments_path:
        compose += "      - MICRO_ENRICHMENTS_PATH=/config/enrichments\n"

    if iglu_registry_url:
        compose += f"      - MICRO_IGLU_REGISTRY_URL={iglu_registry_url}\n"
        if use_env_file:
            # Reference the env var from .env file
            compose += "      - MICRO_IGLU_API_KEY=${SNOWPLOW_IGLU_API_KEY}\n"

    # Add restart policy
    compose += "    restart: unless-stopped\n"

    return compose


def main():
    parser = argparse.ArgumentParser(
        description="Generate Snowplow Micro docker-compose.yml configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic setup
  python setup_micro.py --port 9090

  # With custom schemas
  python setup_micro.py --port 9090 --schemas-path ./my-schemas

  # With Iglu registry (e.g., Snowplow Console)
  python setup_micro.py --port 9090 \\
    --iglu-registry-url https://com-example.iglu.snplow.net/api \\
    --create-env-file
  # Then manually create .env file with: SNOWPLOW_IGLU_API_KEY=your-api-key

  # Full setup with all options
  python setup_micro.py --port 9090 \\
    --schemas-path ./my-schemas \\
    --enrichments-path ./enrichments \\
    --iglu-registry-url https://com-example.iglu.snplow.net/api \\
    --create-env-file
        """
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port for Micro to listen on (default: 9090)"
    )

    parser.add_argument(
        "--schemas-path",
        type=str,
        help="Path to local schemas directory (Iglu-compatible structure)"
    )

    parser.add_argument(
        "--enrichments-path",
        type=str,
        help="Path to enrichment configuration files directory"
    )

    parser.add_argument(
        "--iglu-registry-url",
        type=str,
        help="Iglu registry URL (e.g., https://com-example.iglu.snplow.net/api)"
    )

    parser.add_argument(
        "--create-env-file",
        action="store_true",
        help="Create a .env template file for storing sensitive credentials (recommended)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="docker-compose.yml",
        help="Output file path (default: docker-compose.yml)"
    )

    args = parser.parse_args()

    # Validate inputs
    errors = []

    if args.schemas_path:
        valid, message = validate_schemas_path(args.schemas_path)
        if not valid:
            errors.append(f"Schema validation failed: {message}")
        else:
            print(f"[OK] {message}")

    if args.enrichments_path:
        valid, message = validate_enrichments_path(args.enrichments_path)
        if not valid:
            errors.append(f"Enrichment validation failed: {message}")
        else:
            print(f"[OK] {message}")

    if args.iglu_registry_url:
        valid, message = validate_iglu_registry_url(args.iglu_registry_url)
        if not valid:
            errors.append(f"Iglu registry URL validation failed: {message}")
        else:
            print(f"[OK] {message}")
            if not args.iglu_registry_url.endswith('/api') and 'iglucentral.com' not in args.iglu_registry_url:
                print("[WARNING] Most Iglu registries require '/api' at the end of the URL")

    if errors:
        print("\n[ERROR] Validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    # Provide instructions for .env file if needed
    env_file_path = ".env"
    if args.create_env_file or args.iglu_registry_url:
        if not os.path.exists(env_file_path):
            print(f"\n[ACTION REQUIRED] Create a {env_file_path} file with the following content:")
            print("─" * 60)
            print("# Snowplow Micro environment variables")
            print("# Store sensitive credentials here - this file should be in .gitignore")
            print()
            if args.iglu_registry_url:
                print("# Iglu Registry API Key")
                print("# Get this from your Snowplow Console or Iglu registry provider")
                print("SNOWPLOW_IGLU_API_KEY=your-actual-api-key")
            print("─" * 60)
        else:
            print(f"\n[INFO] {env_file_path} already exists")

    # Generate docker-compose.yml
    compose_content = generate_docker_compose(
        args.port,
        args.schemas_path,
        args.enrichments_path,
        args.iglu_registry_url,
        use_env_file=bool(args.iglu_registry_url)
    )

    # Write to file
    with open(args.output, 'w') as f:
        f.write(compose_content)

    print(f"\n[OK] Generated {args.output}")

    # Check if .gitignore needs updating
    gitignore_path = ".gitignore"
    if args.create_env_file or args.iglu_registry_url:
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                gitignore_content = f.read()
                if '.env' not in gitignore_content:
                    print(f"\n[WARNING] Add '.env' to your {gitignore_path} to avoid committing secrets!")
        else:
            print(f"\n[WARNING] Consider creating a {gitignore_path} with '.env' to avoid committing secrets!")

    # Print next steps
    print("\nNext steps:")
    step = 1
    if args.iglu_registry_url:
        if not os.path.exists(env_file_path):
            print(f"  {step}. Create .env file (see template above) and add your Iglu API key:")
            print("     SNOWPLOW_IGLU_API_KEY=your-actual-api-key")
            step += 1
        else:
            print(f"  {step}. Ensure .env file contains your Iglu API key:")
            print("     SNOWPLOW_IGLU_API_KEY=your-actual-api-key")
            step += 1
    print(f"  {step}. Start Micro:")
    print("     docker compose up -d")
    step += 1
    print(f"\n  {step}. Validate setup:")
    print(f"     python scripts/validate_micro.py --port {args.port}")
    step += 1
    print(f"\n  {step}. Send a test event:")
    print(f"     python scripts/send_test_event.py --port {args.port}")
    step += 1
    print(f"\n  {step}. Check good events:")
    print(f"     python scripts/check_good_bad.py --port {args.port}")


if __name__ == "__main__":
    main()
