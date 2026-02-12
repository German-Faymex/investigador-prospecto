"""Endpoints de generación de email."""
import json

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.post("/email/generate", response_class=HTMLResponse)
async def generate_email(request: Request, research_data: str = Form(...)):
    """Generate SMTYKM email from research results."""
    try:
        from services.researcher import ResearchResult
        from services.email_generator import EmailGenerator

        data = json.loads(research_data)
        research = ResearchResult(**data)

        generator = EmailGenerator()
        email = await generator.generate(research)

        return templates.TemplateResponse(
            "partials/email_editor.html",
            {"request": request, "email": email},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": f"Error generando email: {e}"},
        )
