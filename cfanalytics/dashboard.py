"""Streamlit dashboard for Cloudflare analytics visualization."""

import datetime
import os
from typing import Any, List, Tuple
import duckdb
import plotly.express as px
import streamlit as st

DB_PATH = os.environ.get("CF_DB_PATH", "cloudflare_analytics.duckdb")


@st.cache_resource
def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Establishes a cached, read-only connection to the DuckDB database."""
    if not os.path.exists(DB_PATH):
        st.error(f"Database not found at {DB_PATH}. Run the aggregate CLI first.")
        st.stop()
    return duckdb.connect(DB_PATH, read_only=True)


def render_sidebar(
    conn: duckdb.DuckDBPyConnection,
) -> Tuple[str, str, datetime.date, datetime.date]:
    """Renders the sidebar controls and returns the selected filters."""
    st.sidebar.title("Filters")

    view_mode = st.sidebar.radio("Traffic Type", ["Edge Traffic", "Worker Invocations"])

    if view_mode == "Edge Traffic":
        zones_df = conn.execute(
            "SELECT DISTINCT zone_name FROM edge_requests ORDER BY zone_name"
        ).df()
        available_targets = ["All Zones"] + zones_df["zone_name"].tolist()
        selected_target = st.sidebar.selectbox("Select Zone", available_targets)

        date_query = "SELECT MIN(request_date), MAX(request_date) FROM edge_requests"
    else:
        scripts_df = conn.execute(
            "SELECT DISTINCT script_name FROM worker_invocations ORDER BY script_name"
        ).df()
        available_targets = ["All Scripts"] + scripts_df["script_name"].tolist()
        selected_target = st.sidebar.selectbox("Select Script", available_targets)

        date_query = (
            "SELECT MIN(request_date), MAX(request_date) FROM worker_invocations"
        )

    date_tuple = conn.execute(date_query).fetchone()

    if not date_tuple or date_tuple[0] is None or date_tuple[1] is None:
        st.sidebar.warning("No date data available for this view.")
        st.stop()

    min_date, max_date = date_tuple[0], date_tuple[1]

    date_range = st.sidebar.date_input(
        "Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        return str(view_mode), str(selected_target), date_range[0], date_range[1]

    st.stop()


def build_edge_query_context(
    selected_zone: str, start_date: Any, end_date: Any
) -> Tuple[str, List[Any]]:
    """Constructs the WHERE clause and parameters for edge traffic filters."""
    where_clauses = ["request_date BETWEEN ? AND ?"]
    query_params = [start_date, end_date]

    if selected_zone != "All Zones":
        where_clauses.append("zone_name = ?")
        query_params.append(selected_zone)

    return " AND ".join(where_clauses), query_params


def render_edge_metrics(
    conn: duckdb.DuckDBPyConnection,
    where_sql: str,
    query_params: List[Any],
    selected_zone: str,
) -> None:
    """Renders top-level aggregate edge metrics."""
    st.title(f"Edge Traffic: {selected_zone}")

    req_row = conn.execute(
        f"SELECT SUM(request_count) FROM edge_requests WHERE {where_sql}", query_params
    ).fetchone()
    total_requests = req_row[0] if req_row and req_row[0] is not None else 0

    ip_row = conn.execute(
        f"SELECT COUNT(DISTINCT client_ip) FROM edge_requests WHERE {where_sql}",
        query_params,
    ).fetchone()
    unique_ips = ip_row[0] if ip_row and ip_row[0] is not None else 0

    col1, col2 = st.columns(2)
    col1.metric("Total Requests", f"{total_requests:,}")
    col2.metric("Unique Client IPs", f"{unique_ips:,}")


def render_edge_time_series(
    conn: duckdb.DuckDBPyConnection, where_sql: str, query_params: List[Any]
) -> None:
    """Renders the line chart for top offending IPs over time."""
    st.subheader("Requests Over Time (Top 5 IPs)")

    top_ips_query = f"""
        SELECT client_ip 
        FROM edge_requests 
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
        FROM edge_requests
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
        labels={
            "request_date": "Date",
            "daily_requests": "Requests",
            "client_ip": "Client IP",
        },
    )
    st.plotly_chart(fig, use_container_width=True)


def render_edge_data_tables(
    conn: duckdb.DuckDBPyConnection, where_sql: str, query_params: List[Any]
) -> None:
    """Renders the top paths and top hosts dataframes safely."""
    col_path, col_host = st.columns(2)

    with col_path:
        st.subheader("Top Paths")
        paths_df = conn.execute(
            f"""
            SELECT request_path, SUM(request_count) as total_requests
            FROM edge_requests
            WHERE {where_sql}
            GROUP BY request_path
            ORDER BY total_requests DESC
            LIMIT 10
        """,
            query_params,
        ).df()

        max_paths = 100
        if not paths_df.empty:
            max_paths = int(paths_df["total_requests"].tolist()[0])

        st.dataframe(
            paths_df,
            column_config={
                "request_path": "Path",
                "total_requests": st.column_config.ProgressColumn(
                    "Requests", format="%d", max_value=max_paths
                ),
            },
            hide_index=True,
            use_container_width=True,
        )

    with col_host:
        st.subheader("Top Hosts")
        hosts_df = conn.execute(
            f"""
            SELECT http_host, SUM(request_count) as total_requests
            FROM edge_requests
            WHERE {where_sql}
            GROUP BY http_host
            ORDER BY total_requests DESC
            LIMIT 10
        """,
            query_params,
        ).df()

        max_hosts = 100
        if not hosts_df.empty:
            max_hosts = int(hosts_df["total_requests"].tolist()[0])

        st.dataframe(
            hosts_df,
            column_config={
                "http_host": "Host",
                "total_requests": st.column_config.ProgressColumn(
                    "Requests", format="%d", max_value=max_hosts
                ),
            },
            hide_index=True,
            use_container_width=True,
        )


def render_worker_view(
    conn: duckdb.DuckDBPyConnection,
    selected_script: str,
    start_date: Any,
    end_date: Any,
) -> None:
    """Renders the analytics view for Cloudflare Workers."""
    st.title(f"Worker Invocations: {selected_script}")

    where_clauses = ["request_date BETWEEN ? AND ?"]
    query_params = [start_date, end_date]

    if selected_script != "All Scripts":
        where_clauses.append("script_name = ?")
        query_params.append(selected_script)

    where_sql = " AND ".join(where_clauses)

    req_row = conn.execute(
        f"SELECT SUM(invocation_count) FROM worker_invocations WHERE {where_sql}",
        query_params,
    ).fetchone()
    total_invocations = req_row[0] if req_row and req_row[0] is not None else 0

    st.metric("Total Invocations", f"{total_invocations:,}")

    ts_query = f"""
        SELECT request_date, script_name, SUM(invocation_count) as daily_invocations
        FROM worker_invocations
        WHERE {where_sql}
        GROUP BY request_date, script_name
        ORDER BY request_date ASC
    """
    ts_df = conn.execute(ts_query, query_params).df()

    if not ts_df.empty:
        fig = px.line(
            ts_df,
            x="request_date",
            y="daily_invocations",
            color="script_name",
            markers=True,
            template="plotly_dark",
            labels={
                "request_date": "Date",
                "daily_invocations": "Invocations",
                "script_name": "Script",
            },
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No worker data available for the selected filters.")


def main() -> None:
    """Main application entry point."""
    st.set_page_config(page_title="Cloudflare Analytics", page_icon="☁️", layout="wide")

    conn = get_db_connection()
    view_mode, selected_target, start_date, end_date = render_sidebar(conn)

    if view_mode == "Edge Traffic":
        where_sql, query_params = build_edge_query_context(
            selected_target, start_date, end_date
        )
        render_edge_metrics(conn, where_sql, query_params, selected_target)
        render_edge_time_series(conn, where_sql, query_params)
        render_edge_data_tables(conn, where_sql, query_params)
    else:
        render_worker_view(conn, selected_target, start_date, end_date)


if __name__ == "__main__":
    main()
