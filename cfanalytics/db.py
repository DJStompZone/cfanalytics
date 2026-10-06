"""Database connection and schema management."""

from datetime import date, timedelta
from typing import Any, List
import duckdb
from cfanalytics.models import EdgeAnalyticsRecord, WorkerAnalyticsRecord


class DatabaseManager:
    """Manages the DuckDB database connection and schema."""

    def __init__(self, db_path: str):
        self.conn = duckdb.connect(db_path)
        self._initialize_schema()
        super().__init__()

    def _initialize_schema(self) -> None:
        """Creates the necessary tables if they do not exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS edge_requests (
                zone_name VARCHAR,
                request_date DATE,
                client_ip VARCHAR,
                http_host VARCHAR,
                request_path VARCHAR,
                http_method VARCHAR,
                edge_status_code INTEGER,
                country VARCHAR,
                cache_status VARCHAR,
                request_count INTEGER,
                bytes_transferred UBIGINT
            );
            
            CREATE TABLE IF NOT EXISTS worker_invocations (
                account_id VARCHAR,
                request_date DATE,
                script_name VARCHAR,
                status VARCHAR,
                invocation_count INTEGER,
                cpu_time_p50_us UBIGINT
            );

            CREATE TABLE IF NOT EXISTS aggregation_runs (
                request_date DATE PRIMARY KEY,
                completed_at TIMESTAMP NOT NULL
            );
        """)

        worker_columns = {
            row[1]
            for row in self.conn.execute("PRAGMA table_info('worker_invocations')").fetchall()
        }
        if "status_code" in worker_columns:
            self.conn.execute(
                "ALTER TABLE worker_invocations RENAME COLUMN status_code TO status"
            )
            self.conn.execute(
                "ALTER TABLE worker_invocations ALTER status SET DATA TYPE VARCHAR"
            )
        if "cpu_time_us" in worker_columns:
            self.conn.execute(
                "ALTER TABLE worker_invocations RENAME COLUMN cpu_time_us TO cpu_time_p50_us"
            )

    def insert_edge_records(self, records: List[EdgeAnalyticsRecord]) -> None:
        """Bulk inserts edge analytics records into the database."""
        if not records:
            return

        df_data = [
            (
                r.zone_name,
                r.request_date,
                r.client_ip,
                r.http_host,
                r.request_path,
                r.http_method,
                r.edge_status_code,
                r.country,
                r.cache_status,
                r.request_count,
                r.bytes_transferred,
            )
            for r in records
        ]

        self.conn.executemany(
            """
            INSERT INTO edge_requests 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            df_data,
        )

    def insert_worker_records(self, records: List[WorkerAnalyticsRecord]) -> None:
        """Bulk inserts worker analytics records into the database."""
        if not records:
            return

        df_data = [
            (
                r.account_id,
                r.request_date,
                r.script_name,
                r.status,
                r.invocation_count,
                r.cpu_time_p50_us,
            )
            for r in records
        ]

        self.conn.executemany(
            """
            INSERT INTO worker_invocations 
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            df_data,
        )

    def replace_records_for_date(
        self,
        request_date: str,
        edge_records: List[EdgeAnalyticsRecord],
        worker_records: List[WorkerAnalyticsRecord],
    ) -> None:
        """Atomically replaces all analytics records for a single date."""
        self.conn.execute("BEGIN TRANSACTION")
        try:
            self.conn.execute(
                "DELETE FROM edge_requests WHERE request_date = ?", [request_date]
            )
            self.conn.execute(
                "DELETE FROM worker_invocations WHERE request_date = ?", [request_date]
            )
            self.insert_edge_records(edge_records)
            self.insert_worker_records(worker_records)
            self.conn.execute(
                "DELETE FROM aggregation_runs WHERE request_date = ?", [request_date]
            )
            self.conn.execute(
                """
                INSERT INTO aggregation_runs (request_date, completed_at)
                VALUES (?, current_timestamp)
                """,
                [request_date],
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def get_missing_aggregation_dates(
        self, days: int, end_date: date
    ) -> List[str]:
        """Returns uncompleted dates from a trailing date window."""
        if days < 1:
            raise ValueError("days must be at least 1")

        start_date = end_date - timedelta(days=days - 1)
        completed_dates = {
            row[0]
            for row in self.conn.execute(
                """
                SELECT request_date
                FROM aggregation_runs
                WHERE request_date BETWEEN ? AND ?
                """,
                [start_date, end_date],
            ).fetchall()
        }

        return [
            (start_date + timedelta(days=offset)).isoformat()
            for offset in range(days)
            if start_date + timedelta(days=offset) not in completed_dates
        ]

    def query(self, sql: str) -> List[Any]:
        """Executes a raw SQL query and returns the fetched results."""
        return self.conn.execute(sql).fetchall()
