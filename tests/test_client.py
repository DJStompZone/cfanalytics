"""Tests for Cloudflare API response handling."""

import unittest
from unittest.mock import Mock, patch

import requests

from cfanalytics.client import CloudflareClient, CloudflareGraphQLError


class CloudflareClientTests(unittest.TestCase):
    """Verify GraphQL query construction and error reporting."""

    @patch("cfanalytics.client.requests.post")
    def test_edge_query_uses_valid_http_method_dimension(self, mock_post: Mock) -> None:
        """The edge query asks for the schema's HTTP method dimension."""
        response = Mock()
        response.status_code = 200
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
        response.status_code = 200
        response.json.return_value = {
            "data": None,
            "errors": [{"message": "not authorized for that account"}],
        }
        mock_post.return_value = response

        with self.assertRaisesRegex(
            CloudflareGraphQLError, "not authorized for that account"
        ):
            CloudflareClient("token").get_worker_analytics("account-id", "2026-10-04")

    @patch("cfanalytics.client.requests.post")
    def test_worker_query_uses_a_one_day_time_range(self, mock_post: Mock) -> None:
        """The Worker query uses the documented timestamp filter fields."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": {"viewer": {"accounts": [{"workersInvocationsAdaptive": []}]}}
        }
        mock_post.return_value = response

        CloudflareClient("token").get_worker_analytics("account-id", "2026-10-04")

        query = mock_post.call_args.kwargs["json"]["query"]
        self.assertIn('datetime_geq: "2026-10-04T00:00:00Z"', query)
        self.assertIn('datetime_lt: "2026-10-05T00:00:00Z"', query)

    @patch("cfanalytics.client.time.sleep")
    @patch("cfanalytics.client.requests.post")
    def test_timeout_is_retried_with_exponential_backoff(
        self, mock_post: Mock, mock_sleep: Mock
    ) -> None:
        """A temporary timeout retries before returning analytics data."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": {"viewer": {"zones": [{"httpRequestsAdaptiveGroups": []}]}}
        }
        mock_post.side_effect = [requests.exceptions.ReadTimeout("timed out"), response]

        CloudflareClient("token").get_edge_analytics("zone-id", "2026-10-04")

        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)
