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
    role: str = Form(""),
):
    """Execute prospect research, auto-generate email, and return HTML partial."""
    try:
        from services.researcher import ResearchService
        from services.email_generator import EmailGenerator

        service = ResearchService()
        result = await service.investigate(name, company, role)

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
