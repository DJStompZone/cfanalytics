"""Tests for DuckDB persistence behavior."""

import tempfile
import unittest
from pathlib import Path

from cfanalytics.db import DatabaseManager
from cfanalytics.models import EdgeAnalyticsRecord, WorkerAnalyticsRecord


class DatabaseManagerTests(unittest.TestCase):
    """Verify date-based analytics replacement."""

    def test_replace_records_for_date_replaces_existing_data(self) -> None:
        """A repeat import for one date does not duplicate its records."""
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "analytics.duckdb"
            database = DatabaseManager(str(database_path))
            request_date = "2026-10-04"

            database.replace_records_for_date(
                request_date,
                [
                    EdgeAnalyticsRecord(
                        zone_name="example.com",
                        request_date=request_date,
                        client_ip="192.0.2.1",
                        http_host="example.com",
                        request_path="/first",
                        http_method="GET",
                        edge_status_code=200,
                        country="United States",
                        cache_status="hit",
                        request_count=10,
                        bytes_transferred=100,
                    )
                ],
                [
                    WorkerAnalyticsRecord(
                        account_id="account-1",
                        request_date=request_date,
                        script_name="worker",
                        status_code=200,
                        invocation_count=10,
                        cpu_time_us=100,
                    )
                ],
            )
            database.replace_records_for_date(
                request_date,
                [
                    EdgeAnalyticsRecord(
                        zone_name="example.com",
                        request_date=request_date,
                        client_ip="192.0.2.2",
                        http_host="example.com",
                        request_path="/second",
                        http_method="GET",
                        edge_status_code=200,
                        country="United States",
                        cache_status="miss",
                        request_count=20,
                        bytes_transferred=200,
                    )
                ],
                [
                    WorkerAnalyticsRecord(
                        account_id="account-1",
                        request_date=request_date,
                        script_name="worker",
                        status_code=200,
                        invocation_count=20,
                        cpu_time_us=200,
                    )
                ],
            )

            self.assertEqual(
                database.query("SELECT request_path, request_count FROM edge_requests"),
                [("/second", 20)],
            )
            self.assertEqual(
                database.query(
                    "SELECT invocation_count FROM worker_invocations"
                ),
                [(20,)],
            )
            database.conn.close()
