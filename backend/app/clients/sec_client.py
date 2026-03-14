# filepath: backend/app/clients/sec_client.py
"""
SEC EDGAR HTTP client with token-bucket rate limiting.

Enforces ≤10 requests/second per FR-206.  All requests include the
required ``User-Agent`` header with a contact email address.

SEC EDGAR API endpoints used:
  - ``/submissions/CIK{cik}.json`` — company metadata + recent filings
  - ``/cgi-bin/browse-edgar`` — ticker → CIK resolution
  - ``/api/xbrl/companyfacts/CIK{cik}.json`` — all XBRL financial data
  - ``/Archives/edgar/data/{cik}/{accession}/`` — filing documents

Retry policy (from plan.md):
  - Max retries: 5
  - Backoff: Exponential (2s → 32s)
  - Retry on: 429, 500, 502, 503, ConnectionError, TimeoutError
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Status codes that trigger a retry
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
_MAX_RETRIES = 5
_BASE_BACKOFF_SECONDS = 2.0


class TickerNotFoundError(Exception):
    """Raised when a ticker cannot be resolved to a CIK."""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(f"Ticker '{ticker}' not found on SEC EDGAR")


class SECEdgarError(Exception):
    """Raised on non-retryable SEC EDGAR API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


# =====================================================================
# Token-bucket rate limiter
# =====================================================================


class TokenBucketRateLimiter:
    """Async token-bucket rate limiter.

    Ensures no more than ``max_rate`` requests per second.
    """

    def __init__(self, max_rate: int = 10) -> None:
        self._max_tokens = float(max_rate)
        self._tokens = float(max_rate)
        self._rate = float(max_rate)  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self._max_tokens,
                    self._tokens + elapsed * self._rate,
                )
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                # Wait for enough time to get one token
                wait_time = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait_time)


# =====================================================================
# SEC EDGAR client
# =====================================================================


class SECEdgarClient:
    """Async HTTP client for SEC EDGAR with rate limiting and retries."""

    def __init__(self, settings: Settings | None = None) -> None:
        if settings is None:
            settings = get_settings()
        self._settings = settings
        self._base_url = settings.sec_edgar_base_url.rstrip("/")
        # Filing documents live on www.sec.gov, not data.sec.gov
        self._archives_base_url = self._base_url.replace(
            "data.sec.gov", "www.sec.gov"
        )
        self._user_agent = settings.sec_edgar_user_agent
        self._rate_limiter = TokenBucketRateLimiter(
            max_rate=settings.sec_edgar_rate_limit,
        )
        self._client: httpx.AsyncClient | None = None

    # ── Lifecycle ────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create the httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ── Rate-limited request with retries ────────────────────────

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a rate-limited HTTP request with exponential backoff retries."""
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            await self._rate_limiter.acquire()

            try:
                resp = await client.request(
                    method, url, params=params, headers=headers,
                )

                if resp.status_code == 200:
                    return resp

                if resp.status_code in _RETRYABLE_STATUS_CODES:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and attempt < _MAX_RETRIES:
                        wait = min(float(retry_after), 60.0)
                        logger.warning(
                            "SEC EDGAR rate limited, retrying",
                            status=resp.status_code,
                            retry_after=wait,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(wait)
                        continue

                    if attempt < _MAX_RETRIES:
                        backoff = _BASE_BACKOFF_SECONDS * (2 ** attempt)
                        logger.warning(
                            "SEC EDGAR retryable error",
                            status=resp.status_code,
                            backoff=backoff,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(backoff)
                        continue

                # Non-retryable error
                raise SECEdgarError(
                    f"SEC EDGAR returned HTTP {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                )

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    backoff = _BASE_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning(
                        "SEC EDGAR connection error, retrying",
                        error=str(exc),
                        backoff=backoff,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise SECEdgarError(
                    f"SEC EDGAR unreachable after {_MAX_RETRIES} retries: {exc}",
                ) from last_exc

        raise SECEdgarError("SEC EDGAR request failed after all retries")

    # ── Company resolution ───────────────────────────────────────

    async def resolve_ticker(self, ticker: str) -> dict[str, Any]:
        """Resolve a ticker symbol to company metadata via SEC EDGAR.

        Uses the company tickers JSON endpoint.

        Returns:
            Dict with keys: cik, name, ticker, sic, sic_description,
            state_of_incorporation, fiscal_year_end, etc.

        Raises:
            TickerNotFoundError: If the ticker doesn't exist.
        """
        # Try the tickers JSON first (fastest, no HTML parsing)
        url = f"{self._base_url}/files/company_tickers.json"
        resp = await self._request("GET", url)
        data = resp.json()

        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                cik_str = str(entry["cik_str"]).zfill(10)
                # Fetch full company info
                return await self.get_company_info(cik_str)

        raise TickerNotFoundError(ticker)

    async def get_company_info(self, cik: str) -> dict[str, Any]:
        """Fetch company metadata from the submissions endpoint.

        Args:
            cik: 10-digit zero-padded CIK (e.g. "0000320193").

        Returns:
            Dict with company metadata fields.
        """
        cik_padded = cik.zfill(10)
        url = f"{self._base_url}/submissions/CIK{cik_padded}.json"
        resp = await self._request("GET", url)
        data = resp.json()

        return {
            "cik": cik_padded,
            "name": data.get("name", ""),
            "ticker": (data.get("tickers") or [""])[0] if data.get("tickers") else "",
            "sic": data.get("sic", ""),
            "sic_description": data.get("sicDescription", ""),
            "state_of_incorporation": data.get("stateOfIncorporation", ""),
            "fiscal_year_end": data.get("fiscalYearEnd", ""),
            "entity_type": data.get("entityType", ""),
            "exchanges": data.get("exchanges", []),
        }

    # ── Filing index ─────────────────────────────────────────────

    async def get_filing_index(
        self,
        cik: str,
        *,
        filing_types: list[str] | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get a list of filings for a company from the submissions endpoint.

        Args:
            cik: 10-digit zero-padded CIK.
            filing_types: Filter by form types (e.g. ["10-K", "10-Q"]).
            start_year: Include filings from this year onwards.
            end_year: Include filings up to this year.

        Returns:
            List of filing metadata dicts with keys:
            accessionNumber, filingDate, primaryDocument, form, etc.
        """
        cik_padded = cik.zfill(10)
        url = f"{self._base_url}/submissions/CIK{cik_padded}.json"
        resp = await self._request("GET", url)
        data = resp.json()

        recent = data.get("filings", {}).get("recent", {})
        if not recent:
            return []

        filings: list[dict[str, Any]] = []
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        descriptions = recent.get("primaryDocDescription", [])

        for i in range(len(forms)):
            form = forms[i] if i < len(forms) else ""
            filing_date = dates[i] if i < len(dates) else ""
            accession = accessions[i] if i < len(accessions) else ""
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            description = descriptions[i] if i < len(descriptions) else ""

            # Filter by filing type
            if filing_types and form not in filing_types:
                continue

            # Filter by year range
            if filing_date and (start_year or end_year):
                try:
                    year = int(filing_date[:4])
                    if start_year and year < start_year:
                        continue
                    if end_year and year > end_year:
                        continue
                except ValueError:
                    pass

            filings.append({
                "accession_number": accession,
                "form": form,
                "filing_date": filing_date,
                "primary_document": primary_doc,
                "description": description,
                "filing_url": (
                    f"{self._archives_base_url}/Archives/edgar/data/"
                    f"{int(cik_padded)}/{accession.replace('-', '')}/{primary_doc}"
                ),
            })

        return filings

    # ── XBRL company facts ───────────────────────────────────────

    async def get_company_facts(self, cik: str) -> dict[str, Any]:
        """Fetch all XBRL financial data for a company.

        Uses the ``companyfacts`` endpoint which returns all historical
        US-GAAP and IFRS tagged data in a single response.

        Args:
            cik: 10-digit zero-padded CIK.

        Returns:
            Raw JSON dict from the companyfacts API.
        """
        cik_padded = cik.zfill(10)
        url = f"{self._base_url}/api/xbrl/companyfacts/CIK{cik_padded}.json"
        resp = await self._request("GET", url)
        return resp.json()

    # ── Document download ────────────────────────────────────────

    async def download_filing_document(
        self,
        cik: str,
        accession_number: str,
        document_name: str,
    ) -> bytes:
        """Download a specific filing document from EDGAR archives.

        Args:
            cik: 10-digit zero-padded CIK.
            accession_number: Filing accession (e.g. "0000320193-24-000081").
            document_name: Filename within the filing (e.g. "aapl-20240928.htm").

        Returns:
            Raw document bytes.
        """
        cik_int = int(cik.lstrip("0") or "0")
        accession_clean = accession_number.replace("-", "")
        url = (
            f"{self._archives_base_url}/Archives/edgar/data/"
            f"{cik_int}/{accession_clean}/{document_name}"
        )
        client = await self._get_client()
        await self._rate_limiter.acquire()
        resp = await client.get(url)
        if resp.status_code != 200:
            raise SECEdgarError(
                f"Failed to download {document_name}: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        return resp.content

    # ── Health ───────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if SEC EDGAR is reachable."""
        try:
            client = await self._get_client()
            await self._rate_limiter.acquire()
            resp = await client.get(
                f"{self._base_url}/submissions/CIK0000320193.json",
                headers={"User-Agent": self._user_agent},
            )
            return resp.status_code == 200
        except Exception:
            return False


# =====================================================================
# Module-level singleton
# =====================================================================

_sec_client: SECEdgarClient | None = None


def init_sec_client(settings: Settings | None = None) -> SECEdgarClient:
    """Initialise the module-level SEC EDGAR client singleton."""
    global _sec_client
    _sec_client = SECEdgarClient(settings)
    logger.info("SEC EDGAR client initialised")
    return _sec_client


async def close_sec_client() -> None:
    """Close the module-level SEC EDGAR client."""
    global _sec_client
    if _sec_client is not None:
        await _sec_client.close()
        _sec_client = None


def get_sec_client() -> SECEdgarClient:
    """Return the module-level SEC EDGAR client. Must be initialised first."""
    if _sec_client is None:
        raise RuntimeError(
            "SEC EDGAR client not initialised — call init_sec_client() at startup"
        )
    return _sec_client
