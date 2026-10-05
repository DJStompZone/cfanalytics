"""Database connection and schema management."""
import duckdb
from typing import List, Any
from cfanalytics.models import AnalyticsRecord

class DatabaseManager:
    """Manages the DuckDB database connection and schema."""
    
    def __init__(self, db_path: str):
        self.conn = duckdb.connect(db_path)
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Creates the necessary tables if they do not exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cloudflare_requests (
                zone_name VARCHAR,
                request_date DATE,
                client_ip VARCHAR,
                http_host VARCHAR,
                request_path VARCHAR,
                request_count INTEGER
            )
        """)

    def insert_records(self, records: List[AnalyticsRecord]) -> None:
        """Bulk inserts analytics records into the database."""
        if not records:
            return

        df_data = [
            (
                r.zone_name,
                r.request_date,
                r.client_ip,
                r.http_host,
                r.request_path,
                r.request_count
            )
            for r in records
        ]
        
        self.conn.executemany("""
            INSERT INTO cloudflare_requests 
            (zone_name, request_date, client_ip, http_host, request_path, request_count) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, df_data)
        
    def query(self, sql: str) -> List[Any]:
        """Executes a raw SQL query and returns the fetched results."""
        return self.conn.execute(sql).fetchall()
