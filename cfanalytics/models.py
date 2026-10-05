from pydantic import BaseModel


class EdgeAnalyticsRecord(BaseModel):
    """Expanded record for zone-level HTTP edge traffic."""

    zone_name: str
    request_date: str
    client_ip: str
    http_host: str
    request_path: str
    http_method: str
    edge_status_code: int
    country: str
    cache_status: str
    request_count: int
    bytes_transferred: int


class WorkerAnalyticsRecord(BaseModel):
    """Account-level record for Cloudflare Worker invocations."""

    account_id: str
    request_date: str
    script_name: str
    status: str
    invocation_count: int
    cpu_time_p50_us: int
