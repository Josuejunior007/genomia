"""Demonstração de governança. Estado em memória; não substitui persistência no Supabase."""
from fastapi import APIRouter, HTTPException
from app.schemas.schema import ReviewItem, ReviewRequest, ReviewResponse

router = APIRouter()
suggestions = [
    {"id": 1, "table": "appatendimentoregistro", "kind": "documentation",
     "description": "Registro principal dos atendimentos, identificado por protocolo.",
     "confidence": 0.91, "status": "pending",
     "rationale": "Inferência ilustrativa baseada no nome da tabela e na coluna protocolo."},
    {"id": 2, "table": "boraconversaratendimentos", "kind": "relationship",
     "description": "Não criar FK automática entre responsavelmatricula e boraconversarusuarios.id.",
     "confidence": 0.97, "status": "pending",
     "rationale": "No modelo fornecido, responsavelmatricula representa matrícula funcional, não o id do usuário."},
    {"id": 3, "table": "atendimentosunificados", "kind": "naming",
     "description": "Avaliar nomes descritivos e consistentes para os campos de matrícula.",
     "confidence": 0.63, "status": "pending",
     "rationale": "Sugestão demonstrativa; validar com a pessoa responsável pelo domínio."},
]

@router.get("/suggestions", response_model=list[ReviewItem], summary="Fila demonstrativa de revisão humana")
def list_suggestions(status: str = "pending"):
    if status not in {"pending", "approved", "rejected", "all"}:
        raise HTTPException(status_code=400, detail="Filtro inválido. Use pending, approved, rejected ou all.")
    return [s for s in suggestions if status == "all" or s["status"] == status]

@router.post("/suggestions/{suggestion_id}/review", response_model=ReviewResponse, summary="Aprovar ou rejeitar sugestão demonstrativa")
def review_suggestion(suggestion_id: int, body: ReviewRequest):
    item = next((s for s in suggestions if s["id"] == suggestion_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada.")
    if item["status"] != "pending":
        raise HTTPException(status_code=409, detail="Esta sugestão já foi revisada.")
    item["status"] = body.decision
    return ReviewResponse(id=suggestion_id, status=body.decision, comment=body.comment)
