"""Tests for Cloudflare API response handling."""

import unittest
from unittest.mock import Mock, patch

from cfanalytics.client import CloudflareClient, CloudflareGraphQLError


class CloudflareClientTests(unittest.TestCase):
    """Verify GraphQL query construction and error reporting."""

    @patch("cfanalytics.client.requests.post")
    def test_edge_query_uses_valid_http_method_dimension(self, mock_post: Mock) -> None:
        """The edge query asks for the schema's HTTP method dimension."""
        response = Mock()
        response.json.return_value = {
            "data": {"viewer": {"zones": [{"httpRequestsAdaptiveGroups": []}]}}
        }
        mock_post.return_value = response

        CloudflareClient("token").get_edge_analytics("zone-id", "2026-10-04")

        query = mock_post.call_args.kwargs["json"]["query"]
        self.assertIn("clientRequestHTTPMethodName", query)
        self.assertNotIn("clientRequestMethod", query)

    @patch("cfanalytics.client.requests.post")
    def test_graphql_errors_are_reported(self, mock_post: Mock) -> None:
        """GraphQL errors are not mistaken for an empty analytics result."""
        response = Mock()
        response.json.return_value = {
            "data": None,
            "errors": [{"message": "not authorized for that account"}],
        }
        mock_post.return_value = response

        with self.assertRaisesRegex(
            CloudflareGraphQLError, "not authorized for that account"
        ):
            CloudflareClient("token").get_worker_analytics("account-id", "2026-10-04")
