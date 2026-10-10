from httpx import Client as HttpxClient, Limits, Timeout
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions as ClientOptions

from app.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# postgrest-py hardcodes http2=True on its default client. Under FastAPI's
# threadpool the single shared HTTP/2 connection intermittently dies during
# request bursts (e.g. while a notice is broadcast to thousands of citizens)
# with RemoteProtocolError("Server disconnected"), which surfaced as random
# 500s on unrelated endpoints. A dedicated HTTP/1.1 client spreads concurrent
# queries over pooled connections instead of multiplexing them on one stream.
_http_client = HttpxClient(
    http2=False,
    timeout=Timeout(30.0, connect=10.0),
    limits=Limits(max_connections=20, max_keepalive_connections=10),
)

# This client uses the SERVICE ROLE key: it bypasses Row Level Security entirely.
# Only ever use it here, in server-side code. Every endpoint below is responsible
# for enforcing the same authorization rules RLS would have applied.
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    options=ClientOptions(httpx_client=_http_client),
)
