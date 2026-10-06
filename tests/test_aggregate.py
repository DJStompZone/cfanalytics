"""Tests for analytics aggregation orchestration."""

import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from cfanalytics.aggregate import get_latest_complete_date, run_aggregations


class AggregationTests(unittest.TestCase):
    """Verify account and zone data are combined correctly."""

    def test_latest_complete_date_uses_utc_calendar_day(self) -> None:
        """The backfill window is not shifted by the local timezone."""
        current_time = datetime.fromisoformat("2026-10-06T01:54:34+00:00")

        self.assertEqual(get_latest_complete_date(current_time).isoformat(), "2026-10-05")

    @patch("cfanalytics.aggregate.DatabaseManager")
    @patch("cfanalytics.aggregate.CloudflareClient")
    def test_zone_accounts_are_used_when_account_listing_is_empty(
        self, client_class: Mock, database_class: Mock
    ) -> None:
        """Worker analytics still run when a token can list zones but not accounts."""
        client = client_class.return_value
        client.get_accounts.return_value = []
        client.get_zones.return_value = [
            {
                "id": "zone-1",
                "name": "example.com",
                "account": {"id": "account-1", "name": "Example Account"},
            }
        ]
        client.get_edge_analytics.return_value = []
        client.get_worker_analytics.return_value = []

        run_aggregations("token", "analytics.duckdb", ["2026-10-04"])

        client.get_worker_analytics.assert_called_once_with("account-1", "2026-10-04")
        database_class.return_value.replace_records_for_date.assert_called_once()
