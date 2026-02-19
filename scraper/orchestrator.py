"""Ejecuta los 4 scrapers con stagger para evitar rate limiting."""
import asyncio

from scraper.google_search import GoogleSearchScraper
from scraper.google_news import GoogleNewsScraper
from scraper.linkedin import LinkedInScraper
from scraper.corporate_site import CorporateSiteScraper
from scraper.base import BaseScraper, ScrapedItem


class ScraperOrchestrator:
    def __init__(self):
        self.scrapers = [
            LinkedInScraper(),
            CorporateSiteScraper(),
            GoogleSearchScraper(),
            GoogleNewsScraper(),
        ]

    async def search_all(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        """Ejecuta scrapers con stagger de 1s entre cada uno para evitar rate limiting."""
        async def run_with_delay(scraper, delay):
            if delay > 0:
                await asyncio.sleep(delay)
            return await scraper.search(name, company, role, location)

        # Stagger: LinkedIn y Corporate arrancan inmediato, Google Search a 1s, Google News a 2s
        tasks = [run_with_delay(s, i * 1.0) for i, s in enumerate(self.scrapers)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items = []
        for i, result in enumerate(results):
            if isinstance(result, list):
                all_items.extend(result)
                print(f"[Orchestrator] {self.scrapers[i].__class__.__name__}: {len(result)} resultados")
            elif isinstance(result, Exception):
                print(f"[Orchestrator] {self.scrapers[i].__class__.__name__} error: {result}")

        print(f"[Orchestrator] Total: {len(all_items)} resultados combinados")

        # Limpiar cliente compartido al finalizar
        await BaseScraper.cleanup()

        return all_items
