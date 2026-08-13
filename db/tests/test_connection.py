"""Offline tests for db/connection.py's env-var handling."""
import unittest
from unittest.mock import patch

from db import connection


class TestConnect(unittest.TestCase):
    @patch("db.connection._ensure_env_loaded")
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_env_var_raises_helpful_error(self, _mock_ensure_loaded):
        with self.assertRaises(RuntimeError) as ctx:
            connection._connect("PRERELEASE_DATABASE_URL")
        self.assertIn("PRERELEASE_DATABASE_URL", str(ctx.exception))

    @patch("db.connection.psycopg.connect")
    @patch("db.connection._ensure_env_loaded")
    @patch.dict("os.environ", {"PRERELEASE_DATABASE_URL": "postgresql://fake"}, clear=True)
    def test_connects_with_url_from_env(self, _mock_ensure_loaded, mock_connect):
        connection._connect("PRERELEASE_DATABASE_URL")
        mock_connect.assert_called_once_with("postgresql://fake")


if __name__ == "__main__":
    unittest.main()
