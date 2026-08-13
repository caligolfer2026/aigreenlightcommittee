"""Offline tests for db/prerelease.py -- no live Postgres needed. Every
test mocks out db.connection.get_prerelease_connection and inspects what
SQL/params would have been sent, plus checks the return shape.
"""
import datetime
import unittest
from unittest.mock import MagicMock, patch

from db import prerelease


def _fake_conn(fetchone=None, fetchall=None):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


class TestUpsertFilm(unittest.TestCase):
    @patch("db.prerelease.get_prerelease_connection")
    def test_returns_film_id_and_commits(self, mock_get_conn):
        conn, cursor = _fake_conn(fetchone=(42,))
        mock_get_conn.return_value = conn

        film_id = prerelease.upsert_film(
            tmdb_id=603,
            title="Dune: Part Two",
            release_date="2024-03-01",
            payload={"title": "Dune: Part Two"},
            slate="2026-spring",
        )

        self.assertEqual(film_id, 42)
        conn.commit.assert_called_once()
        conn.close.assert_called_once()
        args, _ = cursor.execute.call_args
        sql, params = args
        self.assertIn("insert into films", sql)
        self.assertIn("on conflict (tmdb_id)", sql)
        self.assertEqual(params[0], 603)
        self.assertEqual(params[3], "2026-spring")


class TestGetSlate(unittest.TestCase):
    @patch("db.prerelease.get_prerelease_connection")
    def test_returns_list_of_films(self, mock_get_conn):
        rows = [(1, 603, "Dune: Part Two", datetime.date(2024, 3, 1), {"title": "Dune: Part Two"})]
        conn, cursor = _fake_conn(fetchall=rows)
        mock_get_conn.return_value = conn

        films = prerelease.get_slate(slate="2026-spring")

        self.assertEqual(len(films), 1)
        self.assertEqual(films[0]["id"], 1)
        self.assertEqual(films[0]["tmdb_id"], 603)
        self.assertEqual(films[0]["release_date"], "2024-03-01")
        self.assertEqual(films[0]["payload"], {"title": "Dune: Part Two"})
        conn.close.assert_called_once()

    @patch("db.prerelease.get_prerelease_connection")
    def test_defaults_to_default_slate(self, mock_get_conn):
        conn, cursor = _fake_conn(fetchall=[])
        mock_get_conn.return_value = conn

        prerelease.get_slate()

        _, params = cursor.execute.call_args[0]
        self.assertEqual(params, ("default",))


class TestVotes(unittest.TestCase):
    @patch("db.prerelease.get_prerelease_connection")
    def test_record_vote_sends_expected_params(self, mock_get_conn):
        conn, cursor = _fake_conn()
        mock_get_conn.return_value = conn

        prerelease.record_vote(
            session_id=1, film_id=1, role="creative", vote="greenlight", argument="Strong cast."
        )

        sql, params = cursor.execute.call_args[0]
        self.assertIn("insert into votes", sql)
        self.assertEqual(params, (1, 1, "creative", "greenlight", "Strong cast."))
        conn.commit.assert_called_once()

    @patch("db.prerelease.get_prerelease_connection")
    def test_get_votes_shapes_rows(self, mock_get_conn):
        now = datetime.datetime(2026, 1, 1, 12, 0, 0)
        rows = [(1, 603, "Dune: Part Two", "creative", "greenlight", "Strong cast.", now)]
        conn, cursor = _fake_conn(fetchall=rows)
        mock_get_conn.return_value = conn

        votes = prerelease.get_votes(session_id=1)

        self.assertEqual(len(votes), 1)
        self.assertEqual(votes[0]["role"], "creative")
        self.assertEqual(votes[0]["vote"], "greenlight")
        self.assertEqual(votes[0]["created_at"], now.isoformat())


if __name__ == "__main__":
    unittest.main()
