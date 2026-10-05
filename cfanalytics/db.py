"""Database connection and schema management."""

from typing import Any, List
import duckdb
from cfanalytics.models import EdgeAnalyticsRecord, WorkerAnalyticsRecord


class DatabaseManager:
    """Manages the DuckDB database connection and schema."""

    def __init__(self, db_path: str):
        self.conn = duckdb.connect(db_path)
        self._initialize_schema()

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
                status_code INTEGER,
                invocation_count INTEGER,
                cpu_time_us UBIGINT
            );
        """)

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
                r.status_code,
                r.invocation_count,
                r.cpu_time_us,
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

    def query(self, sql: str) -> List[Any]:
        """Executes a raw SQL query and returns the fetched results."""
        return self.conn.execute(sql).fetchall()
