"""Orchestration logic to fetch and store analytics."""

import sys
from cfanalytics.client import CloudflareClient
from cfanalytics.db import DatabaseManager
from cfanalytics.models import EdgeAnalyticsRecord, WorkerAnalyticsRecord


def run_aggregation(api_token: str, db_path: str, target_date: str) -> None:
    """Fetches analytics from Cloudflare and stores them in DuckDB."""
    cf_client = CloudflareClient(api_token=api_token)
    db = DatabaseManager(db_path=db_path)

    sys.stdout.write("Fetching accounts and zones...\n")
    accounts = cf_client.get_accounts()
    zones = cf_client.get_zones()

    edge_records = []
    worker_records = []

    for zone in zones:
        zone_id = zone["id"]
        zone_name = zone["name"]
        sys.stdout.write(
            f"Querying edge analytics for {zone_name} on {target_date}...\n"
        )

        nodes = cf_client.get_edge_analytics(zone_id, target_date)
        for node in nodes:
            dimensions = node.get("dimensions", {})
            metrics = node.get("sum", {})
            record = EdgeAnalyticsRecord(
                zone_name=zone_name,
                request_date=target_date,
                client_ip=dimensions.get("clientIP", "UNKNOWN"),
                http_host=dimensions.get("clientRequestHTTPHost", "UNKNOWN"),
                request_path=dimensions.get("clientRequestPath", "UNKNOWN"),
                http_method=dimensions.get("clientRequestMethod", "UNKNOWN"),
                edge_status_code=dimensions.get("edgeResponseStatus", 0),
                country=dimensions.get("clientCountryName", "UNKNOWN"),
                cache_status=dimensions.get("cacheStatus", "UNKNOWN"),
                request_count=node.get("count", 0),
                bytes_transferred=metrics.get("edgeResponseBytes", 0),
            )
            edge_records.append(record)

    for account in accounts:
        account_id = account["id"]
        account_name = account["name"]
        sys.stdout.write(
            f"Querying worker analytics for {account_name} on {target_date}...\n"
        )

        nodes = cf_client.get_worker_analytics(account_id, target_date)
        for node in nodes:
            dimensions = node.get("dimensions", {})
            metrics = node.get("sum", {})
            record = WorkerAnalyticsRecord(
                account_id=account_id,
                request_date=target_date,
                script_name=dimensions.get("scriptName", "UNKNOWN"),
                status_code=dimensions.get("status", 0),
                invocation_count=metrics.get("requests", 0),
                cpu_time_us=metrics.get("cpuTime", 0),
            )
            worker_records.append(record)

    if edge_records:
        db.insert_edge_records(edge_records)
        sys.stdout.write(f"Successfully inserted {len(edge_records)} edge records.\n")
    else:
        sys.stdout.write("No edge records found to insert.\n")

    if worker_records:
        db.insert_worker_records(worker_records)
        sys.stdout.write(
            f"Successfully inserted {len(worker_records)} worker records.\n"
        )
    else:
        sys.stdout.write("No worker records found to insert.\n")
