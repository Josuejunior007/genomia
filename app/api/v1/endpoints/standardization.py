from fastapi import APIRouter, HTTPException
from typing import Any
# Importa o serviço de padronização
from app.services.standardization_Service import StandardizationService

router = APIRouter()
standardization_service = StandardizationService()

@router.post("/validate", response_model=dict)
def validate_naming_standards(schema_data: dict) -> Any:
    """
    Endpoint responsável por validar a padronização de nomes (US14).
    """
    try:
        # Chama o método de validação do serviço
        issues = standardization_service.validate_naming(schema_data)
        
        return {
            "status": "success",
            "message": "Validação de padronização executada com sucesso.",
            "suggestions": issues
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))