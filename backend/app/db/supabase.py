"""Supabase client for database operations."""

import httpx
from app.config import get_settings


class SupabaseClient:
    """Lightweight async Supabase client for SQL execution."""
    
    def __init__(self):
        settings = get_settings()
        self.url = settings.supabase_url
        self.key = settings.supabase_key
        self.db_url = settings.supabase_db_url
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
    
    async def get_customer(self, customer_id: int) -> dict | None:
        """Fetch a customer by ID."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.url}/rest/v1/customers",
                headers={**self.headers, "Accept": "application/json"},
                params={"id": f"eq.{customer_id}", "select": "*"},
            )
            if response.status_code == 200:
                data = response.json()
                return data[0] if data else None
            return None
    
    async def get_customer_billing(self, customer_id: int) -> list[dict]:
        """Fetch billing records for a customer."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.url}/rest/v1/billing",
                headers={**self.headers, "Accept": "application/json"},
                params={
                    "customer_id": f"eq.{customer_id}",
                    "select": "*",
                    "order": "created_at.desc",
                    "limit": "20",
                },
            )
            if response.status_code == 200:
                return response.json()
            return []
    
    async def get_support_tickets(self, customer_id: int) -> list[dict]:
        """Fetch support tickets for a customer."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.url}/rest/v1/support_tickets",
                headers={**self.headers, "Accept": "application/json"},
                params={
                    "customer_id": f"eq.{customer_id}",
                    "select": "*",
                    "order": "created_at.desc",
                },
            )
            if response.status_code == 200:
                return response.json()
            return []
    
    async def search_docs(self, query: str, limit: int = 5) -> list[dict]:
        """Search internal documentation by keyword."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.url}/rest/v1/internal_docs",
                headers={**self.headers, "Accept": "application/json"},
                params={
                    "or": f"(title.ilike.%{query}%,content.ilike.%{query}%,category.ilike.%{query}%)",
                    "select": "id,title,content,category",
                    "limit": str(limit),
                },
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
