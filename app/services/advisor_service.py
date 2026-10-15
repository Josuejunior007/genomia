from app.schemas.schema import AnalysisReport, Recommendation, SchemaSnapshot

def quote_ident(value: str) -> str:
    """Quote PostgreSQL identifiers safely for suggested SQL text."""
    return '"' + value.replace('"', '""') + '"'

class AdvisorService:
    """Regras determinísticas. Recomendações são texto e nunca são executadas."""
    def analyze(self, snapshot: SchemaSnapshot) -> AnalysisReport:
        recs: list[Recommendation] = []
        table_names = {t.name for t in snapshot.tables}
        for table in snapshot.tables:
            if not table.primary_key:
                recs.append(Recommendation(
                    severity="high", table=table.name, category="primary_key",
                    message="Tabela sem chave primária. Avalie se existe uma chave estável.",
                    evidence="A inspeção dos metadados não encontrou uma PK."
                ))
            indexed = {col for idx in table.indexes for col in idx.column_names}
            indexed.update(table.primary_key)
            for fk in table.foreign_keys:
                for col in fk.constrained_columns:
                    if col not in indexed:
                        idx_name = f"idx_{table.name}_{col}"[:60]
                        sql = f"CREATE INDEX {quote_ident(idx_name)} ON {quote_ident(table.schema)}.{quote_ident(table.name)} ({quote_ident(col)});"
                        recs.append(Recommendation(
                            severity="medium", table=table.name, category="index",
                            message=f"A coluna de relacionamento '{col}' não aparece em um índice identificado.",
                            suggested_sql=sql,
                            evidence="Sugestão baseada nos metadados; revise o plano de consulta antes de aplicar."
                        ))
                if fk.referred_table not in table_names:
                    recs.append(Recommendation(
                        severity="high", table=table.name, category="foreign_key",
                        message=f"Referência para tabela não encontrada no snapshot: {fk.referred_table}.",
                        evidence="A tabela referenciada não apareceu na lista de tabelas inspecionadas."
                    ))
            for col in table.columns:
                if col.name.lower() == "id" and col.name not in table.primary_key:
                    recs.append(Recommendation(
                        severity="low", table=table.name, category="naming",
                        message="Existe uma coluna 'id' que não é chave primária; verifique a intenção do modelo.",
                        evidence="Heurística de nomenclatura, requer validação humana."
                    ))
        return AnalysisReport(
            summary=f"{len(snapshot.tables)} tabela(s) analisada(s); {len(recs)} recomendação(ões) encontrada(s).",
            tables_analyzed=len(snapshot.tables), recommendations=recs
        )
