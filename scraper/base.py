"""Base scraper interface y tipos compartidos."""
import asyncio
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

    # Cliente compartido con cookie jar para mantener sesión entre requests
    _shared_client: Optional[httpx.AsyncClient] = None

    # Lock compartido para serializar requests a DDG (evita rate limiting 202)
    _ddg_lock: Optional[asyncio.Lock] = None

    def __init__(self):
        self.settings = get_settings()
        self.headers = {
            "User-Agent": self.settings.scraper.user_agent,
            "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    @classmethod
    def _get_ddg_lock(cls) -> asyncio.Lock:
        """Obtener lock compartido para DDG (lazy init)."""
        if cls._ddg_lock is None:
            cls._ddg_lock = asyncio.Lock()
        return cls._ddg_lock

    @classmethod
    async def _get_client(cls, settings) -> httpx.AsyncClient:
        """Obtener cliente HTTP compartido con cookie jar persistente."""
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(
                timeout=settings.scraper.timeout_seconds,
                follow_redirects=True,
            )
        return cls._shared_client

    @classmethod
    async def cleanup(cls):
        """Cerrar el cliente HTTP compartido."""
        if cls._shared_client and not cls._shared_client.is_closed:
            await cls._shared_client.aclose()
            cls._shared_client = None
        cls._ddg_lock = None  # Reset para próxima sesión

    @abstractmethod
    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        """Buscar información sobre un prospecto."""
        ...

    async def _make_request(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        """Hacer request HTTP con cliente compartido y cookie jar."""
        try:
            client = await self._get_client(self.settings)
            response = await client.get(url, params=params, headers=self.headers)
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

    async def _ddg_post(self, query: str) -> Optional[str]:
        """POST a DuckDuckGo HTML con serialización para evitar rate limiting.

        DDG devuelve 202 cuando recibe muchas requests simultáneas de la misma IP.
        Usamos un Lock compartido entre TODOS los scrapers para serializar acceso.
        """
        lock = self._get_ddg_lock()
        async with lock:
            ddg_url = "https://html.duckduckgo.com/html/"
            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(
                        timeout=self.settings.scraper.timeout_seconds,
                        follow_redirects=True,
                    ) as client:
                        response = await client.post(
                            ddg_url,
                            data={"q": query, "b": ""},
                            headers=self.headers,
                        )
                        if response.status_code == 200:
                            return response.text
                        if response.status_code == 202 and attempt == 0:
                            print(f"[{self.__class__.__name__}] DDG 202, reintentando en 3s")
                            await asyncio.sleep(3)
                            continue
                        print(f"[{self.__class__.__name__}] DDG HTTP {response.status_code}")
                        return None
                except Exception as e:
                    print(f"[{self.__class__.__name__}] DDG error: {e}")
                    return None
            return None
