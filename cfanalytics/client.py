"""Cloudflare API client for REST and GraphQL endpoints."""

from typing import Any, Dict, List
import requests


class CloudflareGraphQLError(RuntimeError):
    """Raised when Cloudflare returns GraphQL errors in a successful HTTP response."""


class CloudflareClient:
    """Client for interacting with Cloudflare REST and GraphQL APIs."""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        super().__init__()

    def _post_graphql(self, query: str, resource: str) -> Dict[str, Any]:
        """Execute a GraphQL query and raise useful errors returned by Cloudflare."""
        response = requests.post(
            f"{self.base_url}/graphql",
            headers=self.headers,
            json={"query": query},
            timeout=15,
        )
        response.raise_for_status()
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
            response = requests.get(
                f"{self.base_url}/accounts",
                headers=self.headers,
                params={"page": page, "per_page": 50},
                timeout=10,
            )
            response.raise_for_status()
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
            response = requests.get(
                f"{self.base_url}/zones",
                headers=self.headers,
                params={"page": page, "per_page": 50},
                timeout=10,
            )
            response.raise_for_status()
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
        query = f"""
        query {{
          viewer {{
            accounts(filter: {{ accountTag: "{account_id}" }}) {{
              workersInvocationsAdaptive(
                limit: 10000,
                filter: {{ date: "{target_date}" }},
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
