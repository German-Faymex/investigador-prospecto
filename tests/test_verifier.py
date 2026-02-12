"""Tests para el verificador de datos cruzados."""
import pytest

from scraper.base import ScrapedItem
from services.verifier import Verifier, VerifiedFact


@pytest.fixture
def verifier():
    return Verifier()


def _item(url, snippet, source):
    return ScrapedItem(url=url, title="", snippet=snippet, source=source)


def test_verified_when_two_sources(verifier):
    items = [
        _item("https://a.com", "CODELCO anuncia inversion de USD 500M en nueva planta", "google_search"),
        _item("https://b.com", "CODELCO invierte USD 500M en planta nueva en Antofagasta", "google_news"),
    ]
    facts = verifier.verify(items)

    assert len(facts) >= 1
    verified = [f for f in facts if f.confidence == "verified"]
    assert len(verified) >= 1
    assert len(verified[0].source_names) >= 2


def test_partial_when_one_source(verifier):
    items = [
        _item("https://a.com", "Roberto Garcia fue nombrado Gerente de Mantenimiento", "google_search"),
    ]
    facts = verifier.verify(items)

    assert len(facts) == 1
    assert facts[0].confidence == "partial"
    assert len(facts[0].sources) == 1


def test_discarded_when_no_url(verifier):
    items = [
        ScrapedItem(url="", title="", snippet="Dato sin fuente verificable con contenido relevante", source="unknown"),
    ]
    facts = verifier.verify(items)

    # Should be discarded (no URL)
    if facts:
        assert facts[0].confidence == "discarded"


def test_empty_items(verifier):
    facts = verifier.verify([])
    assert facts == []


def test_short_snippets_ignored(verifier):
    items = [
        _item("https://a.com", "Hola", "google_search"),
        _item("https://b.com", "", "google_news"),
    ]
    facts = verifier.verify(items)
    assert len(facts) == 0


def test_ordering_verified_first(verifier):
    items = [
        _item("https://a.com", "Dato parcial unico sobre la empresa", "google_search"),
        _item("https://b.com", "CODELCO expansion proyecto nueva planta minera cobre", "google_search"),
        _item("https://c.com", "CODELCO expansion nueva planta minera produccion cobre", "google_news"),
    ]
    facts = verifier.verify(items)

    assert len(facts) >= 1
    # Verified should come first
    if len(facts) >= 2:
        confidence_order = [f.confidence for f in facts]
        verified_idx = [i for i, c in enumerate(confidence_order) if c == "verified"]
        partial_idx = [i for i, c in enumerate(confidence_order) if c == "partial"]
        if verified_idx and partial_idx:
            assert min(verified_idx) < min(partial_idx)


def test_diverse_sources_verified(verifier):
    items = [
        _item("https://linkedin.com/in/roberto", "Roberto Garcia Gerente Mantenimiento CODELCO experiencia mineria", "linkedin"),
        _item("https://news.com/article", "Roberto Garcia asumio como Gerente Mantenimiento en CODELCO mineria", "google_news"),
        _item("https://company.com/team", "Roberto Garcia Gerente de Mantenimiento CODELCO equipo directivo", "corporate"),
    ]
    facts = verifier.verify(items)

    assert len(facts) >= 1
    # Should be verified due to 3 diverse sources with similar content
    verified = [f for f in facts if f.confidence == "verified"]
    assert len(verified) >= 1


def test_unrelated_snippets_separate_groups(verifier):
    items = [
        _item("https://a.com", "CODELCO anuncia nueva planta de procesamiento en Atacama", "google_search"),
        _item("https://b.com", "Roberto Garcia gana premio innovacion en mantenimiento industrial", "google_news"),
    ]
    facts = verifier.verify(items)

    # Should be 2 separate facts (unrelated content)
    assert len(facts) == 2
