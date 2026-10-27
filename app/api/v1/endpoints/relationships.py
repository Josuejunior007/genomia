from fastapi import APIRouter, HTTPException
from typing import Any
# Importa o serviço que criaste na pasta de serviços
from app.services.relationship_service import RelationshipService

router = APIRouter()
relationship_service = RelationshipService()

@router.post("/infer", response_model=dict)
def infer_relationships(schema_data: dict) -> Any:
    """
    Endpoint responsável por identificar relacionamentos implícitos (US13).
    """
    try:
        # Chama o método do serviço passando os dados recebidos na requisição
        suggestions = relationship_service.infer_implicit_relationships(schema_data)
        
        return {
            "status": "success",
            "message": "Análise de relacionamentos implícitos executada com sucesso.",
            "data": suggestions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))