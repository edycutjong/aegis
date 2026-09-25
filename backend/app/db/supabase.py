"""Supabase client for database operations."""

import httpx
from app.config import get_settings


class SupabaseClient:
    """Lightweight async Supabase client for SQL execution."""

    def __init__(self):
        settings = get_settings()
        self.url = settings.supabase_url
        self.key = settings.supabase_key
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    async def execute_sql(self, query: str) -> dict:
        """Execute a SQL query via Supabase REST RPC.

        Uses the rpc endpoint to run raw SQL safely.
        Returns the result rows or an error.
        """
        # Use the Supabase REST API to execute SQL
        # We'll call a custom RPC function that wraps raw SQL
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.url}/rest/v1/rpc/execute_readonly_query",
                headers=self.headers,
                json={"query_text": query.rstrip().rstrip(";")}
            )

            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                }

    async def search_customers(self, name_parts: list[str], limit: int = 5) -> list[dict]:
        """Case-insensitive name search via PostgREST filters.

        Parameters travel as query-string filters, never interpolated into
        SQL, so a ticket's text cannot change the shape of the lookup.
        """
        terms = [p.replace("*", "").replace(",", "").replace("(", "").replace(")", "") for p in name_parts]
        terms = [t for t in terms if t]
        if not terms:
            return []
        filters = ",".join(f"name.ilike.*{t}*" for t in terms)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.url}/rest/v1/customers",
                headers={**self.headers, "Accept": "application/json"},
                params={"select": "id,name,email,plan,status", "and": f"({filters})", "limit": str(limit)},
            )
            if response.status_code == 200:
                return response.json()
            return []

    async def get_billing(self, customer_id: int, limit: int = 100) -> list[dict]:
        """The customer's billing records, fetched directly — the evidence that
        bounds any refund or credit, independent of the SQL the model wrote."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.url}/rest/v1/billing",
                headers={**self.headers, "Accept": "application/json"},
                params={
                    "customer_id": f"eq.{int(customer_id)}",
                    "select": "id,customer_id,amount,type,status,description,created_at",
                    "order": "created_at.desc",
                    "limit": str(limit),
                },
            )
            if response.status_code == 200:
                return response.json()
            return []

    async def list_customers(self, limit: int = 1000) -> list[dict]:
        """Names and emails of every customer, to find who a ticket is about.

        The demo has 51 customers; a real deployment would search (pg_trgm)
        instead of listing.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.url}/rest/v1/customers",
                headers={**self.headers, "Accept": "application/json"},
                params={"select": "id,name,email,company", "order": "id", "limit": str(limit)},
            )
            if response.status_code == 200:
                return response.json()
            return []

    async def list_docs(self, limit: int = 100) -> list[dict]:
        """Fetch the internal knowledge base for in-process ranking."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.url}/rest/v1/internal_docs",
                headers={**self.headers, "Accept": "application/json"},
                params={"select": "id,title,content,category", "order": "id", "limit": str(limit)},
            )
            if response.status_code == 200:
                return response.json()
            return []


# Singleton
_client: SupabaseClient | None = None

def get_supabase() -> SupabaseClient:
    """Get or create the Supabase client singleton."""
    global _client
    if _client is None:
        _client = SupabaseClient()
    return _client
