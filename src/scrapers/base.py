"""Base scraper with rate limiting and common functionality."""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, requests_per_second: float):
        self.rate = requests_per_second
        self.tokens = 1.0
        self.last_update = datetime.now()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request can be made."""
        async with self._lock:
            now = datetime.now()
            elapsed = (now - self.last_update).total_seconds()
            self.tokens = min(1.0, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    # Override in subclasses
    SOURCE_NAME: str = "base"
    BASE_URL: str = ""
    REQUESTS_PER_SECOND: float = 1.0
    USER_AGENT: str = "NHL-Scraper/0.1.0 (analytics research project)"

    def __init__(self):
        self.rate_limiter = RateLimiter(self.REQUESTS_PER_SECOND)
        self.client: httpx.AsyncClient | None = None
        self.logger = logger.bind(source=self.SOURCE_NAME)

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"User-Agent": self.USER_AGENT},
            timeout=30.0,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a rate-limited HTTP request with retries."""
        await self.rate_limiter.acquire()

        if not self.client:
            raise RuntimeError("Scraper not initialized - use async with")

        self.logger.debug("request", method=method, path=path)
        response = await self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        return await self._request("GET", path, **kwargs)

    async def get_json(self, path: str, **kwargs: Any) -> Any:
        """Make a GET request and return JSON."""
        response = await self.get(path, **kwargs)
        return response.json()

    @abstractmethod
    async def scrape_players(self, season: str | None = None) -> list[dict[str, Any]]:
        """Scrape player data."""
        ...

    @abstractmethod
    async def scrape_teams(self) -> list[dict[str, Any]]:
        """Scrape team data."""
        ...

    @abstractmethod
    async def scrape_games(
        self,
        season: str | None = None,
        team_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Scrape game data."""
        ...
