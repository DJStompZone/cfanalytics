"""Command-line interface for the analytics pipeline."""

import argparse
import os
import sys
from cfanalytics.aggregate import get_latest_complete_date, run_aggregation, run_backfill
from cfanalytics.client import CloudflareAPIError
from cfanalytics.visualize import print_top_ips


def run_aggregate(target_date: str | None = None, backfill: bool = False) -> None:
    """Run aggregation for one requested date or all recent missing dates."""
    api_token = os.environ.get("CF_API_TOKEN")
    if not api_token:
        sys.stdout.write("Error: CF_API_TOKEN environment variable is not set.\n")
        sys.exit(1)

    db_path = os.environ.get("CF_DB_PATH", "cloudflare_analytics.duckdb")
    try:
        if backfill:
            run_backfill(api_token, db_path)
            return

        if not target_date:
            target_date = get_latest_complete_date().isoformat()

        run_aggregation(api_token, db_path, target_date)
    except CloudflareAPIError as error:
        sys.stderr.write(f"Error: {error}\n")
        sys.exit(1)


def aggregate_main() -> None:
    """Entry point for the aggregation console script."""
    parser = argparse.ArgumentParser(description="Fetch and store Cloudflare analytics")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--date", help="Target date override (YYYY-MM-DD)")
    mode.add_argument(
        "--backfill", action="store_true", help="Fetch missing dates from the last 30 days"
    )
    args = parser.parse_args()
    run_aggregate(args.date, args.backfill)


def main() -> None:
    """Entry point for the CLI operations."""
    parser = argparse.ArgumentParser(description="Cloudflare Analytics Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    agg_parser = subparsers.add_parser(
        "aggregate", help="Fetch and store yesterday's analytics data"
    )
    mode = agg_parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--date", help="Target date override (YYYY-MM-DD)", default=None
    )
    mode.add_argument(
        "--backfill", action="store_true", help="Fetch missing dates from the last 30 days"
    )

    vis_parser = subparsers.add_parser(
        "visualize", help="Output stored analytics reports"
    )
    vis_parser.add_argument(
        "--limit", type=int, default=10, help="Number of IP results to show"
    )

    args = parser.parse_args()

    if args.command == "aggregate":
        run_aggregate(args.date, args.backfill)

    elif args.command == "visualize":
        db_path = os.environ.get("CF_DB_PATH", "cloudflare_analytics.duckdb")
        print_top_ips(db_path, args.limit)


if __name__ == "__main__":
    main()
