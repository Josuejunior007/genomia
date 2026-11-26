"""Compatibilidade: as rotas de sugestões agora vivem em ``suggestions``.

Este módulo é mantido para imports antigos (``from app.api.v1.endpoints import
demo``). Novos códigos devem importar ``app.api.v1.endpoints.suggestions``.
"""

from app.api.v1.endpoints.suggestions import router

__all__ = ["router"]
