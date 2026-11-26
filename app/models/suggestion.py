"""Modelo de sugestões do GenomAI.

Uma sugestão é sempre uma **proposta textual** produzida por regra
determinística, IA ou pessoa. Ela nunca é executada no banco analisado no
momento em que é criada. A execução, quando permitida, acontece em um endpoint
separado e exige persona ``desenvolvedor`` ou ``administrador``, sugestão
aprovada e configuração explícita de escrita.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, app_table_args


class Suggestion(Base):
    """Proposta persistida no banco interno do GenomAI."""

    __tablename__ = "suggestions"
    __table_args__ = app_table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # Coluna alvo (opcional). Necessária para aplicar comentários de coluna e
    # para gerar índices de forma determinística no endpoint de aplicação.
    column_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    # SQL candidato produzido pela IA. É apenas informativo: nunca é executado
    # diretamente. O endpoint de aplicação gera o SQL a partir de campos
    # validados contra o schema real.
    suggested_sql: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    review_comment: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    edited_by: Mapped[str | None] = mapped_column(String(80), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    apply_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def is_applied(self) -> bool:
        """True quando a mudança já foi aplicada com sucesso no banco alvo."""
        return self.applied_at is not None
