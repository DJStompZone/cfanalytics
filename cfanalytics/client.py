"""Cloudflare API client for REST and GraphQL endpoints."""

from datetime import date, timedelta
import sys
import time
from typing import Any, Dict, List
import requests


class CloudflareAPIError(RuntimeError):
    """Base exception for Cloudflare API failures."""


class CloudflareRequestError(CloudflareAPIError):
    """Raised when a Cloudflare request fails after retrying."""


class CloudflareGraphQLError(CloudflareAPIError):
    """Raised when Cloudflare returns GraphQL errors in a successful HTTP response."""


class CloudflareClient:
    """Client for interacting with Cloudflare REST and GraphQL APIs."""

    max_attempts = 5
    retry_status_codes = {429, 500, 502, 503, 504}
    connect_timeout_seconds = 10
    read_timeout_seconds = 60
    max_backoff_seconds = 30

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        super().__init__()

    def _retry_delay(self, attempt: int, response: requests.Response | None) -> float:
        """Return the next bounded exponential-backoff delay in seconds."""
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(float(retry_after), self.max_backoff_seconds)
                except ValueError:
                    pass

        return min(float(2**attempt), self.max_backoff_seconds)

    def _request_with_retry(
        self, request_method: Any, resource: str, url: str, **kwargs: Any
    ) -> requests.Response:
        """Issue an HTTP request with bounded retries for transient failures."""
        for attempt in range(self.max_attempts):
            response = None
            try:
                response = request_method(
                    url,
                    timeout=(self.connect_timeout_seconds, self.read_timeout_seconds),
                    **kwargs,
                )
                if response.status_code not in self.retry_status_codes:
                    response.raise_for_status()
                    return response
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
                if attempt == self.max_attempts - 1:
                    raise CloudflareRequestError(
                        f"Cloudflare request for {resource} failed after "
                        f"{self.max_attempts} attempts: {error}"
                    ) from error

                delay = self._retry_delay(attempt, None)
                sys.stderr.write(
                    f"Cloudflare request for {resource} failed ({error}). "
                    f"Retrying in {delay:g} seconds...\n"
                )
                time.sleep(delay)
                continue

            if attempt == self.max_attempts - 1:
                raise CloudflareRequestError(
                    f"Cloudflare request for {resource} failed after "
                    f"{self.max_attempts} attempts with HTTP {response.status_code}."
                )

            delay = self._retry_delay(attempt, response)
            sys.stderr.write(
                f"Cloudflare request for {resource} returned HTTP {response.status_code}. "
                f"Retrying in {delay:g} seconds...\n"
            )
            time.sleep(delay)

        raise AssertionError("Retry loop exited unexpectedly")

    def _post_graphql(self, query: str, resource: str) -> Dict[str, Any]:
        """Execute a GraphQL query and raise useful errors returned by Cloudflare."""
        response = self._request_with_retry(
            requests.post,
            resource,
            f"{self.base_url}/graphql",
            headers=self.headers,
            json={"query": query},
        )
        result = response.json()
        errors = result.get("errors")

        if errors:
            messages = "; ".join(
                str(error.get("message", error))
                if isinstance(error, dict)
                else str(error)
                for error in errors
            )
            raise CloudflareGraphQLError(
                f"Cloudflare GraphQL error while querying {resource}: {messages}"
            )

        return result

    def get_accounts(self) -> List[Dict[str, Any]]:
        """Retrieves all accounts associated with the token."""
        accounts = []
        page = 1
        while True:
            response = self._request_with_retry(
                requests.get,
                "account list",
                f"{self.base_url}/accounts",
                headers=self.headers,
                params={"page": page, "per_page": 50},
            )
            data = response.json()
            accounts.extend(data.get("result", []))

            total_pages = data.get("result_info", {}).get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
        return accounts

    def get_zones(self) -> List[Dict[str, Any]]:
        """Retrieves all zones associated with the token via pagination."""
        zones = []
        page = 1
        while True:
            response = self._request_with_retry(
                requests.get,
                "zone list",
                f"{self.base_url}/zones",
                headers=self.headers,
                params={"page": page, "per_page": 50},
            )
            data = response.json()
            zones.extend(data.get("result", []))

            total_pages = data.get("result_info", {}).get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
        return zones

    def get_edge_analytics(
        self, zone_id: str, target_date: str
    ) -> List[Dict[str, Any]]:
        """Retrieves grouped HTTP edge traffic analytics for a specific zone and date."""
        query = f"""
        query {{
          viewer {{
            zones(filter: {{ zoneTag: "{zone_id}" }}) {{
              httpRequestsAdaptiveGroups(
                limit: 10000,
                filter: {{ date: "{target_date}" }},
                orderBy: [count_DESC]
              ) {{
                dimensions {{
                  clientIP
                  clientRequestHTTPHost
                  clientRequestPath
                  clientRequestHTTPMethodName
                  edgeResponseStatus
                  clientCountryName
                  cacheStatus
                }}
                sum {{
                  edgeResponseBytes
                }}
                count
              }}
            }}
          }}
        }}
        """
        result = self._post_graphql(query, f"edge analytics for zone {zone_id}")

        try:
            return result["data"]["viewer"]["zones"][0]["httpRequestsAdaptiveGroups"]
        except (KeyError, IndexError, TypeError):
            return []

    def get_worker_analytics(
        self, account_id: str, target_date: str
    ) -> List[Dict[str, Any]]:
        """Retrieves Worker invocation analytics for a specific account and date."""
        start_date = date.fromisoformat(target_date)
        end_date = start_date + timedelta(days=1)
        query = f"""
        query {{
          viewer {{
            accounts(filter: {{ accountTag: "{account_id}" }}) {{
              workersInvocationsAdaptive(
                limit: 10000,
                filter: {{
                  datetime_geq: "{start_date.isoformat()}T00:00:00Z",
                  datetime_lt: "{end_date.isoformat()}T00:00:00Z"
                }},
                orderBy: [sum_requests_DESC]
              ) {{
                dimensions {{
                  scriptName
                  status
                }}
                sum {{
                  requests
                }}
                quantiles {{
                  cpuTimeP50
                }}
              }}
            }}
          }}
        }}
        """
        result = self._post_graphql(
            query, f"Worker analytics for account {account_id}"
        )

        try:
            return result["data"]["viewer"]["accounts"][0]["workersInvocationsAdaptive"]
        except (KeyError, IndexError, TypeError):
            return []
