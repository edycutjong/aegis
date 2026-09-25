"""Tests for app.db.supabase — SupabaseClient with mocked httpx."""

import os
import pytest
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

            from app.db import supabase as db_mod
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


class TestGetSupabaseSingleton:
    """get_supabase() should return the same instance."""

    def test_returns_singleton(self):
        from app.db import supabase as db_mod
        db_mod._client = None
        c1 = db_mod.get_supabase()
        c2 = db_mod.get_supabase()
        assert c1 is c2
        db_mod._client = None


class TestListDocs:
    """list_docs fetches the knowledge base for in-process ranking."""

    @pytest.mark.asyncio
    async def test_returns_docs_on_200(self, mock_settings):
        from unittest.mock import AsyncMock, MagicMock, patch
        from app.db.supabase import SupabaseClient
        client = SupabaseClient()
        response = MagicMock(status_code=200)
        response.json.return_value = [{"id": 1, "title": "Refund Policy"}]
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value.get = AsyncMock(return_value=response)
            assert await client.list_docs() == [{"id": 1, "title": "Refund Policy"}]

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, mock_settings):
        from unittest.mock import AsyncMock, MagicMock, patch
        from app.db.supabase import SupabaseClient
        client = SupabaseClient()
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value.get = AsyncMock(return_value=MagicMock(status_code=500))
            assert await client.list_docs() == []


class TestListCustomers:
    """list_customers returns the roster used to find who a ticket is about."""

    @pytest.mark.asyncio
    async def test_returns_roster_on_200(self, mock_settings):
        from unittest.mock import AsyncMock, MagicMock, patch
        from app.db.supabase import SupabaseClient
        client = SupabaseClient()
        response = MagicMock(status_code=200)
        response.json.return_value = [{"id": 8, "name": "David Martinez", "email": "d@x.com"}]
        with patch("httpx.AsyncClient") as cls:
            get = AsyncMock(return_value=response)
            cls.return_value.__aenter__.return_value.get = get
            assert await client.list_customers() == [{"id": 8, "name": "David Martinez", "email": "d@x.com"}]
        assert get.call_args.kwargs["params"]["select"] == "id,name,email"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, mock_settings):
        from unittest.mock import AsyncMock, MagicMock, patch
        from app.db.supabase import SupabaseClient
        client = SupabaseClient()
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value.get = AsyncMock(return_value=MagicMock(status_code=500))
            assert await client.list_customers() == []


class TestSearchCustomers:
    """Name search goes through PostgREST filters, never interpolated SQL."""

    @pytest.mark.asyncio
    async def test_builds_and_filter_from_sanitized_parts(self, mock_settings):
        from app.db.supabase import SupabaseClient
        client = SupabaseClient()
        response = MagicMock(status_code=200)
        response.json.return_value = [{"id": 8, "name": "David Martinez"}]
        with patch("httpx.AsyncClient") as cls:
            get = AsyncMock(return_value=response)
            cls.return_value.__aenter__.return_value.get = get
            rows = await client.search_customers(["David", "Mar*ti,n(ez)"])
        assert rows == [{"id": 8, "name": "David Martinez"}]
        params = get.call_args.kwargs["params"]
        assert params["and"] == "(name.ilike.*David*,name.ilike.*Martinez*)"

    @pytest.mark.asyncio
    async def test_empty_terms_short_circuit(self, mock_settings):
        from app.db.supabase import SupabaseClient
        assert await SupabaseClient().search_customers(["*", ""]) == []

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, mock_settings):
        from app.db.supabase import SupabaseClient
        client = SupabaseClient()
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value.get = AsyncMock(return_value=MagicMock(status_code=500))
            assert await client.search_customers(["David"]) == []


class TestGetBilling:
    @pytest.mark.asyncio
    async def test_filters_by_integer_customer_id(self, mock_settings):
        from app.db.supabase import SupabaseClient
        client = SupabaseClient()
        response = MagicMock(status_code=200)
        response.json.return_value = [{"id": 1}]
        with patch("httpx.AsyncClient") as cls:
            get = AsyncMock(return_value=response)
            cls.return_value.__aenter__.return_value.get = get
            assert await client.get_billing(8) == [{"id": 1}]
        assert get.call_args.kwargs["params"]["customer_id"] == "eq.8"

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, mock_settings):
        from app.db.supabase import SupabaseClient
        client = SupabaseClient()
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value.get = AsyncMock(return_value=MagicMock(status_code=500))
            assert await client.get_billing(8) == []
