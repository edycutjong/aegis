"""Tests for app.db.supabase — SupabaseClient with mocked httpx."""

import os
from unittest.mock import patch, AsyncMock, MagicMock



class TestSupabaseClientInit:
    """Verify client initialization from settings."""

    def test_reads_settings(self):
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "SUPABASE_DB_URL": "postgresql://test",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()

            import app.db.supabase as db_mod
            db_mod._client = None
            client = db_mod.get_supabase()

            assert client.url == "https://test.supabase.co"
            assert client.key == "test-key"
            assert "apikey" in client.headers
            assert client.headers["apikey"] == "test-key"


class TestExecuteSQL:
    """execute_sql should handle success and error responses."""

    async def test_success(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "Alice"}]

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.execute_sql("SELECT * FROM customers")

        assert result["success"] is True
        assert result["data"] == [{"id": 1, "name": "Alice"}]

    async def test_error(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"message": "syntax error"}'

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.execute_sql("INVALID SQL")

        assert result["success"] is False
        assert result["status_code"] == 400

    async def test_strips_trailing_semicolon(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            await client.execute_sql("SELECT 1;")
            call_args = mock_client_instance.post.call_args
            assert call_args[1]["json"]["query_text"] == "SELECT 1"


class TestGetCustomer:
    """get_customer should return a dict or None."""

    async def test_found(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "Alice", "plan": "pro"}]

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.get_customer(1)

        assert result == {"id": 1, "name": "Alice", "plan": "pro"}

    async def test_not_found(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.get_customer(999)

        assert result is None

    async def test_api_error(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.get_customer(1)

        assert result is None


class TestGetCustomerBilling:
    """get_customer_billing should return a list."""

    async def test_returns_records(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "amount": 99.99}]

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.get_customer_billing(1)

        assert result == [{"id": 1, "amount": 99.99}]

    async def test_api_error_returns_empty(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.get_customer_billing(1)

        assert result == []


class TestGetSupportTickets:
    """get_support_tickets should return a list."""

    async def test_returns_tickets(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "subject": "Help"}]

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.get_support_tickets(1)

        assert result == [{"id": 1, "subject": "Help"}]

    async def test_api_error_returns_empty(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.get_support_tickets(1)

        assert result == []


class TestSearchDocs:
    """search_docs should return matching documents."""

    async def test_returns_docs(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "title": "Refund Policy", "content": "..."}]

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.search_docs("billing")

        assert len(result) == 1
        assert result[0]["title"] == "Refund Policy"

    async def test_api_error_returns_empty(self):
        from app.db.supabase import SupabaseClient

        client = SupabaseClient.__new__(SupabaseClient)
        client.url = "https://test.supabase.co"
        client.key = "test-key"
        client.headers = {"apikey": "test-key", "Authorization": "Bearer test-key", "Content-Type": "application/json"}

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client.search_docs("billing")

        assert result == []


class TestGetSupabaseSingleton:
    """get_supabase() should return the same instance."""

    def test_returns_singleton(self):
        import app.db.supabase as db_mod
        db_mod._client = None
        c1 = db_mod.get_supabase()
        c2 = db_mod.get_supabase()
        assert c1 is c2
        db_mod._client = None
