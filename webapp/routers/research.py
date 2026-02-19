"""Endpoints de investigación."""
import dataclasses
import json

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.post("/research", response_class=HTMLResponse)
async def do_research(
    request: Request,
    name: str = Form(...),
    company: str = Form(...),
    role: str = Form(...),
    location: str = Form(""),
):
    """Execute prospect research, auto-generate email, and return HTML partial."""
    # Normalizar capitalización del nombre de persona
    name = _title_case(name)

    try:
        from services.researcher import ResearchService
        from services.email_generator import EmailGenerator

        service = ResearchService()
        result = await service.investigate(name, company, role, location)

        if result.error and result.score == 0:
            return templates.TemplateResponse(
                "partials/error.html",
                {"request": request, "error": result.error},
            )

        # Auto-generate email
        email = None
        if result.score > 0:
            try:
                generator = EmailGenerator()
                email = await generator.generate(result)
                print(f"[Research] Email generado automaticamente")
            except Exception as e:
                print(f"[Research] Error generando email: {e}")

        # Convert dataclass to dict for JSON serialization in template
        result_dict = dataclasses.asdict(result)

        return templates.TemplateResponse(
            "partials/research_result.html",
            {
                "request": request,
                "result": result,
                "result_json": json.dumps(result_dict, ensure_ascii=False),
                "name": name,
                "company": company,
                "email": email,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": str(e)},
        )


# Preposiciones/artículos que no se capitalizan en nombres
_LOWERCASE_WORDS = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "con", "da", "do", "dos", "von", "van"}


def _title_case(text: str) -> str:
    """Capitalizar nombres propios respetando preposiciones.

    'gustavo peralta' → 'Gustavo Peralta'
    'juan de la cruz' → 'Juan de la Cruz'
    """
    if not text or not text.strip():
        return text
    words = text.strip().split()
    result = []
    for i, w in enumerate(words):
        if i == 0 or w.lower() not in _LOWERCASE_WORDS:
            # Capitalizar si todo minúsc/mayúsc; preservar mixed case (ej: "McDonald")
            if w.islower() or (w.isupper() and len(w) > 1):
                result.append(w.capitalize())
            else:
                result.append(w)
        else:
            result.append(w.lower())
    return " ".join(result)
