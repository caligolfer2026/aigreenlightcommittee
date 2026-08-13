"""Offline tests for db/results.py -- no live Postgres needed."""
import datetime
import unittest
from unittest.mock import MagicMock, patch

from db import results


def _fake_conn(fetchone=None, fetchall=None):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


class TestActualResults(unittest.TestCase):
    @patch("db.results.get_results_connection")
    def test_upsert_sends_expected_params(self, mock_get_conn):
        conn, cursor = _fake_conn()
        mock_get_conn.return_value = conn

        results.upsert_actual_results(
            tmdb_id=603, title="Dune: Part Two", payload={"boxOfficeDomestic": 100}
        )

        sql, params = cursor.execute.call_args[0]
        self.assertIn("insert into actual_results", sql)
        self.assertEqual(params[0], 603)
        conn.commit.assert_called_once()

    @patch("db.results.get_results_connection")
    def test_get_actual_results_returns_none_when_missing(self, mock_get_conn):
        conn, cursor = _fake_conn(fetchone=None)
        mock_get_conn.return_value = conn

        self.assertIsNone(results.get_actual_results(tmdb_id=999))

    @patch("db.results.get_results_connection")
    def test_get_actual_results_shapes_row(self, mock_get_conn):
        conn, cursor = _fake_conn(fetchone=(603, "Dune: Part Two", {"boxOfficeDomestic": 100}))
        mock_get_conn.return_value = conn

        actual = results.get_actual_results(tmdb_id=603)

        self.assertEqual(actual["tmdb_id"], 603)
        self.assertEqual(actual["payload"], {"boxOfficeDomestic": 100})


class TestScores(unittest.TestCase):
    @patch("db.results.get_results_connection")
    def test_record_score_sends_expected_params(self, mock_get_conn):
        conn, cursor = _fake_conn()
        mock_get_conn.return_value = conn

        results.record_score(session_id=1, tmdb_id=603, grade="B+", rationale="Close call.")

        sql, params = cursor.execute.call_args[0]
        self.assertIn("insert into scores", sql)
        self.assertEqual(params, (1, 603, "B+", "Close call.", None))

    @patch("db.results.get_results_connection")
    def test_get_scores_shapes_rows(self, mock_get_conn):
        now = datetime.datetime(2026, 1, 1, 12, 0, 0)
        rows = [(603, "B+", "Close call.", None, now)]
        conn, cursor = _fake_conn(fetchall=rows)
        mock_get_conn.return_value = conn

        scores = results.get_scores(session_id=1)

        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0]["grade"], "B+")
        self.assertEqual(scores[0]["created_at"], now.isoformat())


if __name__ == "__main__":
    unittest.main()
