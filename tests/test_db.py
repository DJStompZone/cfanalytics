"""Tests for DuckDB persistence behavior."""

import tempfile
import unittest
from pathlib import Path

import duckdb

from cfanalytics.db import DatabaseManager
from cfanalytics.models import EdgeAnalyticsRecord, WorkerAnalyticsRecord


class DatabaseManagerTests(unittest.TestCase):
    """Verify date-based analytics replacement."""

    def test_initialization_migrates_legacy_worker_columns(self) -> None:
        """Existing databases use the current Worker status and CPU columns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "analytics.duckdb"
            legacy_connection = duckdb.connect(str(database_path))
            legacy_connection.execute(
                """
                CREATE TABLE worker_invocations (
                    account_id VARCHAR,
                    request_date DATE,
                    script_name VARCHAR,
                    status_code INTEGER,
                    invocation_count INTEGER,
                    cpu_time_us UBIGINT
                )
                """
            )
            legacy_connection.close()

            database = DatabaseManager(str(database_path))
            columns = database.query("PRAGMA table_info('worker_invocations')")
            column_names = {column[1] for column in columns}

            self.assertIn("status", column_names)
            self.assertIn("cpu_time_p50_us", column_names)
            self.assertNotIn("status_code", column_names)
            self.assertNotIn("cpu_time_us", column_names)
            database.conn.close()

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
                        status="success",
                        invocation_count=10,
                        cpu_time_p50_us=100,
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
                        status="success",
                        invocation_count=20,
                        cpu_time_p50_us=200,
                    )
                ],
            )

            self.assertEqual(
                database.query("SELECT request_path, request_count FROM edge_requests"),
                [("/second", 20)],
            )
            self.assertEqual(
                database.query("SELECT invocation_count FROM worker_invocations"),
                [(20,)],
            )
            database.conn.close()
