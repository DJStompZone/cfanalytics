"""Orchestration logic to fetch and store analytics."""
import sys
from cfanalytics.client import CloudflareClient
from cfanalytics.db import DatabaseManager
from cfanalytics.models import AnalyticsRecord

def run_aggregation(api_token: str, db_path: str, target_date: str) -> None:
    """Fetches analytics from Cloudflare and stores them in DuckDB."""
    cf_client = CloudflareClient(api_token=api_token)
    db = DatabaseManager(db_path=db_path)

    sys.stdout.write("Fetching zones...\n")
    zones = cf_client.get_zones()
    
    all_records = []
    for zone in zones:
        zone_id = zone["id"]
        zone_name = zone["name"]
        sys.stdout.write(f"Querying analytics for {zone_name} on {target_date}...\n")
        
        nodes = cf_client.get_daily_analytics(zone_id, target_date)
        for node in nodes:
            dimensions = node.get("dimensions", {})
            record = AnalyticsRecord(
                zone_name=zone_name,
                request_date=target_date,
                client_ip=dimensions.get("clientIP", "UNKNOWN"),
                http_host=dimensions.get("clientRequestHTTPHost", "UNKNOWN"),
                request_path=dimensions.get("clientRequestPath", "UNKNOWN"),
                request_count=node.get("count", 0)
            )
            all_records.append(record)

    if all_records:
        db.insert_records(all_records)
        sys.stdout.write(f"Successfully inserted {len(all_records)} records into DuckDB.\n")
    else:
        sys.stdout.write("No records found to insert.\n")
