"""Command-line interface for the analytics pipeline."""
import argparse
import datetime
import os
import sys
from cfanalytics.aggregate import run_aggregation
from cfanalytics.visualize import print_top_ips

def main() -> None:
    """Entry point for the CLI operations."""
    parser = argparse.ArgumentParser(description="Cloudflare Analytics Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    agg_parser = subparsers.add_parser("aggregate", help="Fetch and store yesterday's analytics data")
    agg_parser.add_argument("--date", help="Target date override (YYYY-MM-DD)", default=None)
    
    vis_parser = subparsers.add_parser("visualize", help="Output stored analytics reports")
    vis_parser.add_argument("--limit", type=int, default=10, help="Number of IP results to show")

    args = parser.parse_args()
    
    db_path = os.environ.get("CF_DB_PATH", "cloudflare_analytics.duckdb")

    if args.command == "aggregate":
        api_token = os.environ.get("CF_API_TOKEN")
        if not api_token:
            sys.stdout.write("Error: CF_API_TOKEN environment variable is not set.\n")
            sys.exit(1)
            
        target_date = args.date
        if not target_date:
            target_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
            
        run_aggregation(api_token, db_path, target_date)
        
    elif args.command == "visualize":
        print_top_ips(db_path, args.limit)

if __name__ == "__main__":
    main()
