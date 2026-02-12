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
    """Execute prospect research and return HTML partial."""
    try:
        from services.researcher import ResearchService

        service = ResearchService()
        result = await service.investigate(name, company, role)

        if result.error and result.score == 0:
            return templates.TemplateResponse(
                "partials/error.html",
                {"request": request, "error": result.error},
            )

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
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": str(e)},
        )
