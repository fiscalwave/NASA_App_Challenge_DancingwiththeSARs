"""
NASA Earthdata Login (EDL) bearer-token management.

Why this exists: real HTTPS partial-read access to NISAR GCOV files via
fsspec (see GCOVReader.load_gcov_subset_remote() in app/processing/gcov_reader.py) requires an
`Authorization: Bearer <token>` header - a different auth mechanism from
the username/password session cookie that asf-search's ASFSession (used by
DownloadManager for whole-file downloads) relies on. This module mints and
caches a real EDL user token from the same existing ASF_USERNAME/ASF_PASSWORD
credentials already configured for this app, using NASA's documented
find_or_create_token API (reuses an existing valid token for this user if
one exists, rather than minting a new one every time - EDL only allows two
concurrent valid tokens per user).

Tokens are valid for 60 days. This module caches the token in memory and
refreshes it automatically once it is within REFRESH_MARGIN of expiring (or
if a request using it ever fails with 401/403), so a long-running server
process never needs a manual restart to pick up a fresh token.
"""

from __future__ import annotations

import base64
import threading
import time
from typing import Optional

import requests

from app.utils.errors import DataIngestionError
from app.utils.logging import get_logger

logger = get_logger(__name__)

EDL_TOKEN_URL = "https://urs.earthdata.nasa.gov/api/users/find_or_create_token"

# EDL user tokens are valid 60 days; refresh proactively well before expiry
# so a request never races a token that's about to be rejected.
TOKEN_LIFETIME_SECONDS = 60 * 24 * 60 * 60
REFRESH_MARGIN_SECONDS = 3 * 24 * 60 * 60  # refresh with 3 days to spare


class EDLTokenManager:
    """Thread-safe cache/refresh of a real EDL bearer token for one
    Earthdata account. Never fabricates or hardcodes a token - always
    mints/reuses a real one via NASA's own API using real configured
    credentials."""

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._minted_at: float = 0.0

    def _mint_token(self) -> str:
        basic = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        try:
            resp = requests.post(
                EDL_TOKEN_URL,
                headers={"Authorization": f"Basic {basic}"},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise DataIngestionError(f"Could not obtain an EDL bearer token: {e}")

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise DataIngestionError(f"EDL token response did not include access_token: {data}")

        logger.info("Minted a real EDL bearer token (find_or_create_token)")
        return token

    def get_token(self, force_refresh: bool = False) -> str:
        """Return a real, currently-valid EDL bearer token, minting or
        reusing one as needed. Thread-safe - concurrent callers will not
        mint duplicate tokens (EDL caps a user at 2 concurrent valid tokens)."""
        with self._lock:
            age = time.time() - self._minted_at
            needs_refresh = (
                force_refresh
                or self._token is None
                or age > (TOKEN_LIFETIME_SECONDS - REFRESH_MARGIN_SECONDS)
            )
            if needs_refresh:
                self._token = self._mint_token()
                self._minted_at = time.time()
            return self._token


_manager: Optional[EDLTokenManager] = None
_manager_lock = threading.Lock()


def get_edl_token_manager(username: str, password: str) -> EDLTokenManager:
    """Module-level singleton so the whole app shares one cached/refreshed
    token per process instead of each caller minting its own."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = EDLTokenManager(username, password)
        return _manager
