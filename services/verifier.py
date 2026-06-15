"""Verificación cruzada de datos entre fuentes."""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse

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

    @staticmethod
    def _domain(url: str) -> str:
        """Dominio normalizado de una URL (sin www), para contar fuentes únicas."""
        try:
            return urlparse(url).netloc.replace("www.", "").lower()
        except Exception:
            return ""

    def verify(self, items: list[ScrapedItem]) -> list[VerifiedFact]:
        """Agrupar snippets similares y asignar confianza según diversidad de fuentes."""
        if not items:
            return []

        # Agrupar snippets similares
        groups: list[dict] = []

        for item in items:
            # Usar snippet como texto principal; si snippet es muy corto, usar title como fallback
            text = item.snippet.strip() if item.snippet else ""
            if len(text) < 10 and item.title and len(item.title.strip()) >= 10:
                text = item.title.strip()
                item.snippet = text  # Promover title a snippet para el resto del pipeline
            elif len(text) < 10:
                continue

            tokens = _tokenize(text)
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

            # Confianza basada en FUENTES INDEPENDIENTES, no en número de
            # scrapers. Google y DDG que devuelven la MISMA URL/dominio (ej:
            # ambos indexan el mismo perfil de LinkedIn) NO son dos fuentes:
            # es la misma página encontrada dos veces. Contamos dominios web
            # distintos; Perplexity cuenta como una fuente extra (su propia
            # búsqueda web), aunque su cita sea de un dominio ya contado.
            non_pplx_domains = {
                self._domain(it.url)
                for it in group_items
                if it.url and not it.source.startswith("perplexity")
            }
            non_pplx_domains.discard("")
            has_perplexity = any(it.source.startswith("perplexity") for it in group_items)
            independent_sources = len(non_pplx_domains) + (1 if has_perplexity else 0)

            if independent_sources >= 2:
                confidence = "verified"
            elif independent_sources >= 1:
                # Una sola fuente real (incluye Perplexity sola) → parcial
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
