"""Cloudflare API client for REST and GraphQL endpoints."""
import requests
from typing import Any, Dict, List

class CloudflareClient:
    """Client for interacting with Cloudflare REST and GraphQL APIs."""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def get_zones(self) -> List[Dict[str, Any]]:
        """Retrieves all zones associated with the account via pagination."""
        zones = []
        page = 1
        while True:
            response = requests.get(
                f"{self.base_url}/zones",
                headers=self.headers,
                params={"page": page, "per_page": 50},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            zones.extend(data.get("result", []))
            
            total_pages = data.get("result_info", {}).get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
        return zones

    def get_daily_analytics(self, zone_id: str, target_date: str) -> List[Dict[str, Any]]:
        """Retrieves grouped HTTP request analytics for a specific zone and date."""
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
                }}
                count
              }}
            }}
          }}
        }}
        """
        response = requests.post(
            f"{self.base_url}/graphql",
            headers=self.headers,
            json={"query": query},
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        
        try:
            return result["data"]["viewer"]["zones"][0]["httpRequestsAdaptiveGroups"]
        except (KeyError, IndexError, TypeError):
            return []
