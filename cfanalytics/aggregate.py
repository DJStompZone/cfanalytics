"""Orchestration logic to fetch and store analytics."""

import datetime
import sys

from cfanalytics.client import CloudflareClient
from cfanalytics.db import DatabaseManager
from cfanalytics.models import EdgeAnalyticsRecord, WorkerAnalyticsRecord


def get_latest_complete_date(
    current_time: datetime.datetime | None = None,
) -> datetime.date:
    """Return yesterday's date in UTC, when Cloudflare's daily data is complete."""
    if current_time is None:
        current_time = datetime.datetime.now(datetime.UTC)
    return current_time.date() - datetime.timedelta(days=1)


def run_aggregation(api_token: str, db_path: str, target_date: str) -> None:
    """Fetch and store analytics for one date."""
    run_aggregations(api_token, db_path, [target_date])


def run_backfill(api_token: str, db_path: str, days: int = 30) -> None:
    """Fetch the most recent completed-date gaps without reprocessing marked dates."""
    db = DatabaseManager(db_path)
    end_date = get_latest_complete_date()
    target_dates = db.get_missing_aggregation_dates(days, end_date)
    db.conn.close()

    if not target_dates:
        sys.stdout.write(f"No missing dates found in the last {days} days.\n")
        return

    sys.stdout.write(
        f"Backfilling {len(target_dates)} missing date(s) from the last {days} days.\n"
    )
    run_aggregations(api_token, db_path, target_dates)


def run_aggregations(
    api_token: str, db_path: str, target_dates: list[str]
) -> None:
    """Fetch and store analytics for dates using one account and zone lookup."""
    cf_client = CloudflareClient(api_token=api_token)
    db = DatabaseManager(db_path=db_path)

    sys.stdout.write("Fetching accounts and zones...\n")
    accounts = cf_client.get_accounts()
    zones = cf_client.get_zones()

    accounts_by_id = {account["id"]: account for account in accounts}
    for zone in zones:
        account = zone.get("account", {})
        account_id = account.get("id")
        if account_id:
            accounts_by_id.setdefault(account_id, account)
    accounts = list(accounts_by_id.values())

    for target_date in target_dates:
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
                    http_method=dimensions.get("clientRequestHTTPMethodName", "UNKNOWN"),
                    edge_status_code=dimensions.get("edgeResponseStatus", 0),
                    country=dimensions.get("clientCountryName", "UNKNOWN"),
                    cache_status=dimensions.get("cacheStatus", "UNKNOWN"),
                    request_count=node.get("count", 0),
                    bytes_transferred=metrics.get("edgeResponseBytes", 0),
                )
                edge_records.append(record)

        for account in accounts:
            account_id = account["id"]
            account_name = account.get("name", account_id)
            sys.stdout.write(
                f"Querying Worker analytics for {account_name} on {target_date}...\n"
            )

            nodes = cf_client.get_worker_analytics(account_id, target_date)
            for node in nodes:
                dimensions = node.get("dimensions", {})
                metrics = node.get("sum", {})
                quantiles = node.get("quantiles", {})
                record = WorkerAnalyticsRecord(
                    account_id=account_id,
                    request_date=target_date,
                    script_name=dimensions.get("scriptName", "UNKNOWN"),
                    status=dimensions.get("status", "UNKNOWN"),
                    invocation_count=metrics.get("requests", 0),
                    cpu_time_p50_us=quantiles.get("cpuTimeP50", 0),
                )
                worker_records.append(record)

        db.replace_records_for_date(target_date, edge_records, worker_records)

        if edge_records:
            sys.stdout.write(
                f"Successfully inserted {len(edge_records)} edge records.\n"
            )
        else:
            sys.stdout.write("No edge records found to insert.\n")

        if worker_records:
            sys.stdout.write(
                f"Successfully inserted {len(worker_records)} Worker records.\n"
            )
        else:
            sys.stdout.write("No Worker records found to insert.\n")
