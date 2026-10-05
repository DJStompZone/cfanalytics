"""Streamlit dashboard for Cloudflare analytics visualization."""

import os
import streamlit as st
import duckdb
import plotly.express as px
from typing import Tuple, List, Any

DB_PATH = os.environ.get("CF_DB_PATH", "cloudflare_analytics.duckdb")

@st.cache_resource
def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Establishes a cached, read-only connection to the DuckDB database."""
    if not os.path.exists(DB_PATH):
        st.error(f"Database not found at {DB_PATH}. Run the aggregate CLI first.")
        st.stop()
    return duckdb.connect(DB_PATH, read_only=True)

def render_sidebar(conn: duckdb.DuckDBPyConnection) -> Tuple[str, Any, Any]:
    """Renders the sidebar controls and returns the selected filters."""
    st.sidebar.title("Filters")

    zones_df = conn.execute("SELECT DISTINCT zone_name FROM cloudflare_requests ORDER BY zone_name").df()
    available_zones = ["All Zones"] + zones_df["zone_name"].tolist()
    selected_zone = st.sidebar.selectbox("Select Zone", available_zones)

    min_date, max_date = conn.execute("SELECT MIN(request_date), MAX(request_date) FROM cloudflare_requests").fetchone()
    
    if not min_date or not max_date:
        st.sidebar.warning("No date data available.")
        st.stop()

    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        return selected_zone, date_range[0], date_range[1]
    
    st.stop()

def build_query_context(selected_zone: str, start_date: Any, end_date: Any) -> Tuple[str, List[Any]]:
    """Constructs the WHERE clause and parameters for the selected filters."""
    where_clauses = ["request_date BETWEEN ? AND ?"]
    query_params = [start_date, end_date]

    if selected_zone != "All Zones":
        where_clauses.append("zone_name = ?")
        query_params.append(selected_zone)

    return " AND ".join(where_clauses), query_params

def render_metrics(conn: duckdb.DuckDBPyConnection, where_sql: str, query_params: List[Any], selected_zone: str) -> None:
    """Renders top-level aggregate metrics."""
    st.title(f"Traffic Overview: {selected_zone}")

    total_requests = conn.execute(f"""
        SELECT SUM(request_count) 
        FROM cloudflare_requests 
        WHERE {where_sql}
    """, query_params).fetchone()[0] or 0

    unique_ips = conn.execute(f"""
        SELECT COUNT(DISTINCT client_ip) 
        FROM cloudflare_requests 
        WHERE {where_sql}
    """, query_params).fetchone()[0] or 0

    col1, col2 = st.columns(2)
    col1.metric("Total Requests", f"{total_requests:,}")
    col2.metric("Unique Client IPs", f"{unique_ips:,}")

def render_time_series(conn: duckdb.DuckDBPyConnection, where_sql: str, query_params: List[Any]) -> None:
    """Renders the line chart for top offending IPs over time."""
    st.subheader("Requests Over Time (Top 5 IPs)")

    top_ips_query = f"""
        SELECT client_ip 
        FROM cloudflare_requests 
        WHERE {where_sql}
        GROUP BY client_ip 
        ORDER BY SUM(request_count) DESC 
        LIMIT 5
    """
    top_ips = [row[0] for row in conn.execute(top_ips_query, query_params).fetchall()]

    if not top_ips:
        st.info("No data available for the selected filters.")
        return

    placeholders = ",".join(["?"] * len(top_ips))
    ts_params = query_params + top_ips
    
    ts_query = f"""
        SELECT request_date, client_ip, SUM(request_count) as daily_requests
        FROM cloudflare_requests
        WHERE {where_sql} AND client_ip IN ({placeholders})
        GROUP BY request_date, client_ip
        ORDER BY request_date ASC
    """
    ts_df = conn.execute(ts_query, ts_params).df()

    fig = px.line(
        ts_df, 
        x="request_date", 
        y="daily_requests", 
        color="client_ip",
        markers=True,
        template="plotly_dark",
        labels={"request_date": "Date", "daily_requests": "Requests", "client_ip": "Client IP"}
    )
    st.plotly_chart(fig, use_container_width=True)

def render_data_tables(conn: duckdb.DuckDBPyConnection, where_sql: str, query_params: List[Any]) -> None:
    """Renders the top paths and top hosts dataframes."""
    col_path, col_host = st.columns(2)

    with col_path:
        st.subheader("Top Paths")
        paths_df = conn.execute(f"""
            SELECT request_path, SUM(request_count) as total_requests
            FROM cloudflare_requests
            WHERE {where_sql}
            GROUP BY request_path
            ORDER BY total_requests DESC
            LIMIT 10
        """, query_params).df()
        
        st.dataframe(
            paths_df,
            column_config={
                "request_path": "Path",
                "total_requests": st.column_config.ProgressColumn(
                    "Requests", 
                    format="%d", 
                    max_value=int(paths_df["total_requests"].max()) if not paths_df.empty else 100
                )
            },
            hide_index=True,
            use_container_width=True
        )

    with col_host:
        st.subheader("Top Hosts")
        hosts_df = conn.execute(f"""
            SELECT http_host, SUM(request_count) as total_requests
            FROM cloudflare_requests
            WHERE {where_sql}
            GROUP BY http_host
            ORDER BY total_requests DESC
            LIMIT 10
        """, query_params).df()
        
        st.dataframe(
            hosts_df,
            column_config={
                "http_host": "Host",
                "total_requests": st.column_config.ProgressColumn(
                    "Requests", 
                    format="%d", 
                    max_value=int(hosts_df["total_requests"].max()) if not hosts_df.empty else 100
                )
            },
            hide_index=True,
            use_container_width=True
        )

def main() -> None:
    """Main application entry point."""
    st.set_page_config(
        page_title="Cloudflare Analytics", 
        page_icon="", 
        layout="wide"
    )
    
    conn = get_db_connection()
    selected_zone, start_date, end_date = render_sidebar(conn)
    where_sql, query_params = build_query_context(selected_zone, start_date, end_date)
    
    render_metrics(conn, where_sql, query_params, selected_zone)
    render_time_series(conn, where_sql, query_params)
    render_data_tables(conn, where_sql, query_params)

if __name__ == "__main__":
    main()
