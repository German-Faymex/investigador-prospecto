"""Base scraper interface y tipos compartidos."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx

from config.settings import get_settings


@dataclass
class ScrapedItem:
    url: str
    title: str
    snippet: str
    source: str  # "google_search", "google_news", "linkedin", "corporate"
    timestamp: str = ""


class BaseScraper(ABC):
    """Interfaz base para todos los scrapers."""

    def __init__(self):
        self.settings = get_settings()
        self.headers = {
            "User-Agent": self.settings.scraper.user_agent,
            "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    @abstractmethod
    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        """Buscar información sobre un prospecto."""
        ...

    async def _make_request(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        """Hacer request HTTP con manejo de errores."""
        timeout = self.settings.scraper.timeout_seconds
        try:
            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    return response.text
                print(f"[{self.__class__.__name__}] HTTP {response.status_code} para {url}")
                return None
        except httpx.TimeoutException:
            print(f"[{self.__class__.__name__}] Timeout para {url}")
            return None
        except httpx.HTTPError as e:
            print(f"[{self.__class__.__name__}] Error HTTP: {e}")
            return None
