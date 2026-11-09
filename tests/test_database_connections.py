import socket
import unittest
from unittest.mock import patch

from psycopg.conninfo import conninfo_to_dict

import database


class PostgresConninfoTests(unittest.TestCase):
    def setUp(self):
        self.original_url = database.SUPABASE_DB_URL
        database.SUPABASE_DB_URL = (
            "postgresql://db-user:db-password@db.example.com:5432/app"
            "?sslmode=require"
        )

    def tearDown(self):
        database.SUPABASE_DB_URL = self.original_url

    @patch("database.socket.getaddrinfo")
    def test_prefers_ipv4_and_keeps_hostname(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("192.0.2.10", 5432))
        ]

        params = conninfo_to_dict(database._postgres_conninfo())

        self.assertEqual(params["host"], "db.example.com")
        self.assertEqual(params["hostaddr"], "192.0.2.10")
        self.assertEqual(params["sslmode"], "require")

    @patch("database.socket.getaddrinfo", side_effect=socket.gaierror(socket.EAI_NONAME, "no IPv4"))
    def test_keeps_original_conninfo_when_no_ipv4_address_exists(self, _getaddrinfo):
        self.assertEqual(database._postgres_conninfo(), database.SUPABASE_DB_URL)


if __name__ == "__main__":
    unittest.main()
