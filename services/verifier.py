"""Verificación cruzada de datos entre fuentes."""
import re
from collections import defaultdict
from dataclasses import dataclass, field

from scraper.base import ScrapedItem


@dataclass
class VerifiedFact:
    content: str
    sources: list[str] = field(default_factory=list)  # URLs
    source_names: list[str] = field(default_factory=list)  # Nombres de scrapers
    confidence: str = "discarded"  # "verified", "partial", "discarded"


def _tokenize(text: str) -> set[str]:
    """Extraer tokens significativos de un texto."""
    text = text.lower()
    text = re.sub(r"[^\w\sáéíóúñü]", " ", text)
    words = text.split()
    # Filtrar stopwords comunes en español e inglés
    stopwords = {
        "de", "la", "el", "en", "y", "a", "los", "las", "del", "un", "una",
        "que", "es", "por", "con", "para", "su", "se", "al", "lo", "como",
        "más", "o", "pero", "sus", "le", "ha", "me", "si", "sin", "sobre",
        "este", "ya", "entre", "cuando", "todo", "esta", "ser", "son", "dos",
        "the", "and", "is", "in", "of", "to", "for", "with", "on", "at",
        "from", "by", "an", "be", "has", "was", "are", "or", "as", "it",
    }
    return {w for w in words if len(w) > 2 and w not in stopwords}


def _similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Jaccard similarity entre dos sets de tokens."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


class Verifier:
    """Verifica hechos cruzando datos de múltiples fuentes."""

    SIMILARITY_THRESHOLD = 0.25

    def verify(self, items: list[ScrapedItem]) -> list[VerifiedFact]:
        """Agrupar snippets similares y asignar confianza según diversidad de fuentes."""
        if not items:
            return []

        # Agrupar snippets similares
        groups: list[dict] = []

        for item in items:
            if not item.snippet or len(item.snippet.strip()) < 10:
                continue

            tokens = _tokenize(item.snippet)
            if not tokens:
                continue

            matched = False
            for group in groups:
                if _similarity(tokens, group["tokens"]) >= self.SIMILARITY_THRESHOLD:
                    group["items"].append(item)
                    group["tokens"] |= tokens
                    matched = True
                    break

            if not matched:
                groups.append({
                    "tokens": tokens,
                    "items": [item],
                })

        # Construir VerifiedFacts
        facts = []
        for group in groups:
            group_items: list[ScrapedItem] = group["items"]

            # Usar el snippet más largo como contenido representativo
            best_snippet = max(group_items, key=lambda x: len(x.snippet))

            # Seleccionar el mejor title del grupo
            best_title_item = max(group_items, key=lambda x: len(x.title)) if any(it.title for it in group_items) else None
            best_title = best_title_item.title if best_title_item else ""

            content = best_snippet.snippet
            if best_title:
                title_tokens = _tokenize(best_title)
                snippet_tokens = _tokenize(content)
                if title_tokens - snippet_tokens:  # title tiene info no redundante
                    content = f"{best_title}. {content}"

            urls = list({it.url for it in group_items if it.url})
            source_names = list({it.source for it in group_items})

            # Confianza basada en diversidad de fuentes (scrapers distintos)
            unique_sources = len(source_names)
            if unique_sources >= 2:
                confidence = "verified"
            elif unique_sources == 1 and urls:
                confidence = "partial"
            else:
                confidence = "discarded"

            facts.append(VerifiedFact(
                content=content,
                sources=urls,
                source_names=source_names,
                confidence=confidence,
            ))

        # Ordenar: verified primero, luego partial, luego discarded
        order = {"verified": 0, "partial": 1, "discarded": 2}
        facts.sort(key=lambda f: order.get(f.confidence, 3))

        return facts
