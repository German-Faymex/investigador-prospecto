"""JSON Schemas para structured outputs de los LLM.

Estos esquemas se aplican en dos niveles:
- Anthropic (Haiku): enforcement real vía output_config.format (la API garantiza
  que la respuesta valida contra el esquema).
- DeepSeek: solo modo json_object (JSON válido garantizado, sin enforcement de
  esquema); el esquema sirve como señal para activar ese modo.
"""

_STR = {"type": "string"}
_STR_ARRAY = {"type": "array", "items": {"type": "string"}}

RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "persona": {
            "type": "object",
            "properties": {
                "nombre": _STR,
                "cargo": _STR,
                "empresa": _STR,
                "linkedin": _STR,
                "trayectoria": _STR,
                "educacion": _STR,
                "intereses": _STR,
                "ubicacion": _STR,
                "logros_recientes": _STR_ARRAY,
                "experiencia_previa": _STR_ARRAY,
            },
            "required": [
                "nombre", "cargo", "empresa", "linkedin", "trayectoria",
                "educacion", "intereses", "ubicacion",
                "logros_recientes", "experiencia_previa",
            ],
            "additionalProperties": False,
        },
        "empresa": {
            "type": "object",
            "properties": {
                "nombre": _STR,
                "industria": _STR,
                "tamano_empleados": _STR,
                "descripcion": _STR,
                "noticias_recientes": _STR_ARRAY,
                "productos_servicios": _STR_ARRAY,
                "desafios_sector": _STR_ARRAY,
                "competidores": _STR_ARRAY,
                "ubicacion": _STR,
                "presencia": _STR,
                "sitio_web": _STR,
            },
            "required": [
                "nombre", "industria", "tamano_empleados", "descripcion",
                "noticias_recientes", "productos_servicios", "desafios_sector",
                "competidores", "ubicacion", "presencia", "sitio_web",
            ],
            "additionalProperties": False,
        },
        "hallazgos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content": _STR,
                    "tipo": {"type": "string", "enum": ["A", "B", "C", "D"]},
                    "sources": _STR_ARRAY,
                    "confidence": {
                        "type": "string",
                        "enum": ["verified", "partial", "unverified"],
                    },
                },
                "required": ["content", "tipo", "sources", "confidence"],
                "additionalProperties": False,
            },
        },
        "hallazgo_tipo": {"type": "string", "enum": ["A", "B", "C", "D"]},
        "score": {"type": "integer"},
        "cargo_descubierto": _STR,
    },
    "required": [
        "persona", "empresa", "hallazgos", "hallazgo_tipo",
        "score", "cargo_descubierto",
    ],
    "additionalProperties": False,
}

EMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "asunto": _STR,
        "cuerpo_html": _STR,
        "cuerpo_texto": _STR,
        "razonamiento": _STR,
    },
    "required": ["asunto", "cuerpo_html", "cuerpo_texto", "razonamiento"],
    "additionalProperties": False,
}
