# cfanalytics

`cfanalytics` collects Cloudflare HTTP edge and Worker invocation analytics, stores the results locally in DuckDB, and presents them in a Streamlit dashboard.

It is intended for lightweight, self-hosted reporting across every account and zone that an API token can access.

## Features

- Retrieves zone-level HTTP edge traffic, including client IP, host, path, method, response status, country, cache status, request count, and bytes transferred.
- Retrieves Cloudflare Worker invocation totals, grouped by script and status.
- Stores daily aggregates in a portable DuckDB database.
- Provides a filterable Streamlit dashboard for edge traffic and Worker trends.

## Requirements

- Python `3.13` or later (but below Python 4)
- `pip`
- A Cloudflare API token authorized to list the intended accounts and zones and read their analytics data

## Installation

Clone the repository and install it from the project root:

```bash
git clone https://github.com/DJStompZone/cfanalytics.git
cd cfanalytics
python -m pip install .
```

On Windows, use `py -3.13 -m pip install .` if `python` does not select Python 3.13. On Linux and macOS, use `python3 -m pip install .` if that is how Python 3.13 is installed.

## Quick Start

Set your Cloudflare API token for the current shell.

### Windows PowerShell

```powershell
$env:CF_API_TOKEN = "your-token"
cfanalytics-aggregate
cfanalytics-dashboard
```

### Linux/macOS Bash

```bash
export CF_API_TOKEN="your-token"
cfanalytics-aggregate
cfanalytics-dashboard
```

The aggregation command imports yesterday's data by default. After at least one successful import, Streamlit prints a local URL for the dashboard.

To import a specific date instead:

```text
cfanalytics-aggregate --date 2026-10-04
```

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `CF_API_TOKEN` | For `aggregate` | Not set | Cloudflare API token used by the REST and GraphQL requests. |
| `CF_DB_PATH` | No | `cloudflare_analytics.duckdb` | Path to the DuckDB database used by the CLI and dashboard. |

To keep the database outside the repository, set `CF_DB_PATH` before running either command.

### Windows PowerShell

```powershell
$env:CF_DB_PATH = "$HOME\data\cloudflare_analytics.duckdb"
cfanalytics-aggregate --date 2026-10-04
cfanalytics-dashboard
```

### Linux/macOS Bash

```bash
export CF_DB_PATH="$HOME/data/cloudflare_analytics.duckdb"
cfanalytics-aggregate --date 2026-10-04
cfanalytics-dashboard
```

## CLI Reference

### `cfanalytics-aggregate`

Fetches all accessible accounts and zones, requests their analytics for a single day, and stores the returned records in DuckDB.

```text
cfanalytics-aggregate [--date YYYY-MM-DD]
```

When `--date` is omitted, the command uses yesterday's date. It requires `CF_API_TOKEN`.

### `cfanalytics-dashboard`

Starts the Streamlit dashboard:

```text
cfanalytics-dashboard
```

### `cfanalytics`

Provides the original subcommand interface. `cfanalytics aggregate [--date YYYY-MM-DD]` is equivalent to `cfanalytics-aggregate [--date YYYY-MM-DD]`.

The `cfanalytics visualize --limit <n>` subcommand is intended to print the most active client IPs. The current database schema uses the `edge_requests` table, while this report still queries the legacy `cloudflare_requests` table. Until that is reconciled, use the Streamlit dashboard or query DuckDB directly.

## Dashboard

The dashboard opens with filters for a date range and either a zone or Worker script.

- **Edge Traffic** shows total requests, unique client IPs, daily activity for the five busiest IPs, and top paths and hosts.
- **Worker Invocations** shows total invocations and daily invocations by script.

The dashboard connects to DuckDB in read-only mode and displays an actionable error if the database has not been created yet.

## Stored Data

The database is created automatically on the first aggregation run.

| Table | Contents |
| --- | --- |
| `edge_requests` | Zone HTTP request aggregates by date, client IP, host, path, method, response status, country, and cache status. |
| `worker_invocations` | Worker invocation aggregates by account, date, script, status, and P50 CPU time. |

You can explore the data using DuckDB, for example:

```sql
SELECT
  zone_name,
  SUM(request_count) AS requests
FROM edge_requests
GROUP BY zone_name
ORDER BY requests DESC;
```

## Operational Notes

- Re-running aggregation for a date replaces all stored edge and Worker records for that date. The replacement is transactional, so a failed database write leaves the previous data intact.
- The database may contain client IP addresses and request paths. Store it securely and follow your organization's data-retention and privacy requirements.
- A token's accessible accounts and zones determine what data is imported.

## License

This project is licensed under the [MIT License](LICENSE).
