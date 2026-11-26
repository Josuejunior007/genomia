"""Privacidade: construção do único payload de metadados enviado à IA.

Princípios (aplicados por código, não apenas por instrução de prompt):

1. A IA recebe **somente** o resultado de :func:`build_safe_schema_context`.
2. O construtor usa uma *allowlist* de campos. Qualquer campo novo no snapshot
   só chega ao payload se for adicionado explicitamente aqui.
3. Valores padrão de coluna, amostras e registros nunca são copiados.
4. Identificadores são limpos: e-mails, UUIDs, sequências longas de dígitos e
   tokens são redigidos.
5. Colunas com nomes ligados a dados pessoais/sensíveis são marcadas e, se
   configurado, pseudonimizadas.
6. Tabelas do armazenamento interno do GenomAI são excluídas por padrão.
7. O payload é validado por :func:`assert_safe_payload` antes de qualquer
   chamada de rede, e um hash SHA-256 é registrado para auditoria.

Este módulo não importa o cliente de IA nem o banco interno. Ele é uma camada
pura, testável e reutilizável por outros provedores de IA.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from enum import Enum
from typing import Any, Iterable

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.schema import AnalysisReport, SchemaSnapshot


class SensitivityCategory(str, Enum):
    """Categorias de dado pessoal/sensível reconhecidas por nome de coluna."""

    IDENTIFICACAO = "identificacao"
    CONTATO = "contato"
    ENDERECO = "endereco"
    SAUDE = "saude"
    FINANCEIRO = "financeiro"
    AUTENTICACAO = "autenticacao"
    PROFISSIONAL = "profissional"
    BIOMETRIA = "biometria"


# A ordem importa: categorias mais específicas vêm primeiro.
_SENSITIVE_PATTERNS: tuple[tuple[SensitivityCategory, re.Pattern[str]], ...] = (
    (
        SensitivityCategory.AUTENTICACAO,
        re.compile(
            r"(senha|password|passwd|passphrase|token|secret|credencial|credential|"
            r"api[_ ]?key|access[_ ]?key|private[_ ]?key|hash|salt|otp|mfa)",
            re.IGNORECASE,
        ),
    ),
    (
        SensitivityCategory.BIOMETRIA,
        re.compile(r"(biometr|impressao[_ ]?digital|facial|iris|reconhecimento)", re.IGNORECASE),
    ),
    (
        SensitivityCategory.SAUDE,
        re.compile(
            r"(saude|doenca|diagnostico|medicamento|medicacao|exame|prontuario|"
            r"deficiencia|alergia|sangue|psicolog|mental|terapia|cid|internacao|"
            r"atestado|vacina|gestante|gravidez)",
            re.IGNORECASE,
        ),
    ),
    (
        SensitivityCategory.FINANCEIRO,
        re.compile(
            r"(cartao|card|conta[_ ]?bancaria|agencia|pix|salario|renda|banco|"
            r"iban|swift|financeir|fatura|boleto|cripto|investimento)",
            re.IGNORECASE,
        ),
    ),
    (
        SensitivityCategory.ENDERECO,
        re.compile(
            r"(endereco|address|logradouro|rua|avenida|bairro|cep|zip|cidade|"
            r"municipio|estado|uf|pais|geolocal|latitude|longitude|coordenada)",
            re.IGNORECASE,
        ),
    ),
    (
        SensitivityCategory.CONTATO,
        re.compile(
            r"(email|e[_ ]?mail|mail|telefone|fone|celular|whatsapp|phone|contato|"
            r"recado|sms)",
            re.IGNORECASE,
        ),
    ),
    (
        SensitivityCategory.IDENTIFICACAO,
        re.compile(
            r"(cpf|cnpj|rg|passaporte|documento|identidade|nascimento|birth|"
            r"nome|name|sobrenome|surname|apelido|nickname|titulo[_ ]?eleitor|"
            r"certidao|registro[_ ]?civil|filiacao|mae|pai|responsavel[_ ]?legal)",
            re.IGNORECASE,
        ),
    ),
    (
        SensitivityCategory.PROFISSIONAL,
        re.compile(
            r"(matricula|matrícula|funcionario|colaborador|employee|usuario|user|"
            r"login|perfil|cargo|salario|admissao|demissao|cracha|ponto)",
            re.IGNORECASE,
        ),
    ),
)

# Padrões de *valor* que podem aparecer acidentalmente em nomes/defaults.
_VALUE_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE), "<email>"),
    (
        re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.IGNORECASE,
        ),
        "<uuid>",
    ),
    (re.compile(r"\b(sk|pk|ghp|gho|glpat|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b"), "<token>"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "<jwt>"),
    (re.compile(r"(?<!\d)\d{6,}(?!\d)"), "<numeros>"),
    (re.compile(r"\b\+?55?\s?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b"), "<telefone>"),
    # Evita que caracteres de controle quebrem o JSON ou o prompt.
    (re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"), ""),
)

# Campos que jamais podem existir no payload. A checagem é por chave exata,
# para não confundir "is_primary_key" (metadado seguro) com "key" (segredo).
FORBIDDEN_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "default",
        "defaults",
        "default_value",
        "default_values",
        "row",
        "rows",
        "record",
        "records",
        "sample",
        "samples",
        "sample_values",
        "values",
        "data",
        "raw",
        "content",
        "contents",
        "password",
        "senha",
        "token",
        "secret",
        "api_key",
    }
)

SAFE_METADATA_POLICY = "safe-metadata-v1"
MAX_IDENTIFIER_LENGTH = 128


class SafeColumn(BaseModel):
    """Coluna exposta à IA: estrutura e marcação de sensibilidade, sem valores."""

    name: str
    type: str
    nullable: bool
    is_primary_key: bool
    sensitive: bool = False
    sensitivity_category: str | None = None


class SafeForeignKey(BaseModel):
    """Chave estrangeira com nomes de colunas já sanitizados."""

    constrained_columns: list[str]
    referred_table: str
    referred_schema: str
    referred_columns: list[str]


class SafeIndex(BaseModel):
    """Índice estrutural, sem estatísticas ou valores."""

    name: str
    column_names: list[str]
    unique: bool


class SafeTable(BaseModel):
    """Tabela exposta à IA, somente com metadados permitidos."""

    name: str
    columns: list[SafeColumn]
    primary_key: list[str]
    foreign_keys: list[SafeForeignKey]
    indexes: list[SafeIndex]


class SafeSchemaContext(BaseModel):
    """Payload final e imutável enviado ao provedor de IA."""

    schema_name: str
    tables: list[SafeTable]
    policy: str = SAFE_METADATA_POLICY


class PrivacyReport(BaseModel):
    """Resumo do que foi enviado e do que foi removido/redigido."""

    tables_included: int = 0
    tables_excluded: int = 0
    columns_included: int = 0
    sensitive_columns: int = 0
    redacted_identifiers: int = 0
    removed_fields: int = 0
    masked_sensitive_identifiers: bool = False
    excluded_table_names: list[str] = Field(default_factory=list)
    notice: str = (
        "Somente metadados estruturais. Nenhum registro, valor de coluna ou "
        "valor padrão é enviado à IA."
    )


class SafeAiPayload(BaseModel):
    """Payload pronto para envio + relatório de privacidade + hash."""

    payload: SafeSchemaContext
    report: PrivacyReport
    sha256: str


def _normalized(value: str) -> str:
    """Normaliza para comparação (sem acentos, minúsculas)."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def classify_sensitive(name: str) -> SensitivityCategory | None:
    """Classifica o nome de uma coluna em uma categoria sensível, se aplicável."""
    normalized = _normalized(name)
    for category, pattern in _SENSITIVE_PATTERNS:
        if pattern.search(normalized):
            return category
    return None


def sanitize_identifier(
    value: str,
    *,
    redact_digit_runs: bool = True,
    max_length: int = MAX_IDENTIFIER_LENGTH,
) -> tuple[str, int]:
    """Redige padrões de valor em um identificador e devolve ``(texto, N)``."""
    text = str(value)
    redactions = 0
    for pattern, replacement in _VALUE_REDACTIONS:
        if pattern.pattern == r"(?<!\d)\d{6,}(?!\d)" and not redact_digit_runs:
            continue
        text, count = pattern.subn(replacement, text)
        redactions += count
    text = " ".join(text.split())
    if len(text) > max_length:
        text = text[:max_length]
        redactions += 1
    return (text or "identificador_removido"), redactions


def _map_columns(
    columns: Iterable[str],
    mapping: dict[str, str],
) -> list[str]:
    return [mapping.get(column, mapping.get("*", column)) for column in columns]


def build_safe_schema_context(
    snapshot: SchemaSnapshot,
    *,
    excluded_tables: Iterable[str] | None = None,
    mask_sensitive: bool | None = None,
    redact_digit_runs: bool | None = None,
) -> SafeAiPayload:
    """Transforma um snapshot em payload seguro para IA.

    Args:
        snapshot: metadados lidos do banco analisado (nunca linhas).
        excluded_tables: nomes a excluir além dos configurados na aplicação.
        mask_sensitive: se ``True``, pseudonimiza colunas sensíveis.
        redact_digit_runs: se ``True``, redige sequências de 6+ dígitos.

    Returns:
        Payload imutável, relatório de privacidade e hash SHA-256 canônico.
    """
    mask = (
        settings.privacy_mask_sensitive_identifiers
        if mask_sensitive is None
        else mask_sensitive
    )
    redact_digits = (
        settings.privacy_redact_digit_runs
        if redact_digit_runs is None
        else redact_digit_runs
    )

    excluded = {
        item.strip().casefold()
        for item in (excluded_tables or settings.analysis_excluded_tables)
        if item and item.strip()
    }
    report = PrivacyReport(
        masked_sensitive_identifiers=mask,
        excluded_table_names=sorted(excluded),
    )

    safe_tables: list[SafeTable] = []
    for table in sorted(snapshot.tables, key=lambda item: item.name.casefold()):
        if table.name.casefold() in excluded:
            report.tables_excluded += 1
            continue

        table_name, table_redactions = sanitize_identifier(
            table.name, redact_digit_runs=redact_digits
        )
        report.redacted_identifiers += table_redactions

        mapping: dict[str, str] = {}
        safe_columns: list[SafeColumn] = []
        for index, column in enumerate(table.columns, start=1):
            category = classify_sensitive(column.name)
            safe_name, redactions = sanitize_identifier(
                column.name, redact_digit_runs=redact_digits
            )
            report.redacted_identifiers += redactions
            if category is not None:
                report.sensitive_columns += 1
                if mask:
                    safe_name = f"coluna_sensivel_{index:02d}"
            mapping[column.name] = safe_name
            safe_columns.append(
                SafeColumn(
                    name=safe_name,
                    type=sanitize_identifier(column.type, redact_digit_runs=False)[0],
                    nullable=bool(column.nullable),
                    is_primary_key=bool(column.is_primary_key),
                    sensitive=category is not None,
                    sensitivity_category=category.value if category else None,
                )
            )

        # O nome da tabela também pode ser sensível; nesse caso, a referência
        # permanece apenas com o nome sanitizado.
        safe_table = SafeTable(
            name=table_name,
            columns=safe_columns,
            primary_key=_map_columns(table.primary_key, mapping),
            foreign_keys=[],
            indexes=[],
        )

        for foreign_key in table.foreign_keys:
            if foreign_key.referred_table.casefold() in excluded:
                # Não revela nem referencia uma tabela do armazenamento interno.
                report.removed_fields += 1
                continue
            referred_name, referred_redactions = sanitize_identifier(
                foreign_key.referred_table, redact_digit_runs=redact_digits
            )
            report.redacted_identifiers += referred_redactions
            safe_referred_columns: list[str] = []
            for referred_column in foreign_key.referred_columns:
                # Colunas referenciadas pertencem a outra tabela; o mapping local
                # não se aplica. Sanitizamos separadamente para não vazar valores
                # embutidos no nome.
                safe_column, column_redactions = sanitize_identifier(
                    referred_column, redact_digit_runs=redact_digits
                )
                report.redacted_identifiers += column_redactions
                safe_referred_columns.append(safe_column)
            safe_table.foreign_keys.append(
                SafeForeignKey(
                    constrained_columns=_map_columns(
                        foreign_key.constrained_columns, mapping
                    ),
                    referred_table=referred_name,
                    referred_schema=sanitize_identifier(
                        foreign_key.referred_schema, redact_digit_runs=False
                    )[0],
                    referred_columns=safe_referred_columns,
                )
            )
        # Deduplica FKs idênticas após mapeamento de colunas.
        seen_fks: set[tuple[Any, ...]] = set()
        unique_fks: list[SafeForeignKey] = []
        for fk in safe_table.foreign_keys:
            key = (
                tuple(fk.constrained_columns),
                fk.referred_schema,
                fk.referred_table,
                tuple(fk.referred_columns),
            )
            if key not in seen_fks:
                seen_fks.add(key)
                unique_fks.append(fk)
        safe_table.foreign_keys = unique_fks

        for index_info in table.indexes:
            safe_index_name, index_redactions = sanitize_identifier(
                index_info.name, redact_digit_runs=redact_digits
            )
            report.redacted_identifiers += index_redactions
            safe_table.indexes.append(
                SafeIndex(
                    name=safe_index_name,
                    column_names=_map_columns(index_info.column_names, mapping),
                    unique=bool(index_info.unique),
                )
            )

        report.columns_included += len(safe_columns)
        report.tables_included += 1
        safe_tables.append(safe_table)

    payload = SafeSchemaContext(
        schema_name=sanitize_identifier(snapshot.schema, redact_digit_runs=False)[0],
        tables=safe_tables,
    )
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return SafeAiPayload(
        payload=payload,
        report=report,
        sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    """Percorre recursivamente o payload para validação."""
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def assert_safe_payload(payload: dict[str, Any] | BaseModel) -> None:
    """Falha se o payload contiver chaves proibidas (linhas/defaults/segredos)."""
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    for path, value in _walk(data):
        if isinstance(value, dict):
            for key in value:
                if str(key).casefold() in FORBIDDEN_PAYLOAD_KEYS:
                    raise ValueError(
                        f"Payload de IA contém campo proibido {key!r} em {path}."
                    )
    # Strings muito longas podem indicar um valor de dado copiado por engano.
    for path, value in _walk(data):
        if isinstance(value, str) and len(value) > 4000:
            raise ValueError(f"Payload de IA contém texto suspeito em {path}.")


def sanitize_text(value: str, *, max_length: int = 4000) -> str:
    """Sanitiza textos derivados (mensagens, evidências, SQL candidato)."""
    text, _ = sanitize_identifier(value, redact_digit_runs=True, max_length=max_length)
    return text


def sanitize_deterministic_report(report: AnalysisReport) -> dict[str, Any]:
    """Versão segura dos achados determinísticos enviados junto ao prompt."""
    return {
        "summary": sanitize_text(report.summary),
        "tables_analyzed": report.tables_analyzed,
        "recommendations": [
            {
                "severity": item.severity,
                "table": sanitize_identifier(item.table)[0],
                "category": sanitize_identifier(item.category)[0],
                "message": sanitize_text(item.message),
                "suggested_sql": sanitize_text(item.suggested_sql) if item.suggested_sql else None,
                "evidence": sanitize_text(item.evidence) if item.evidence else None,
            }
            for item in report.recommendations
        ],
    }


def privacy_policy_payload() -> dict[str, Any]:
    """Descreve a política de privacidade para documentação e frontend."""
    return {
        "policy": SAFE_METADATA_POLICY,
        "allowed_fields": [
            "schema_name",
            "table.name",
            "table.primary_key",
            "table.columns[].name",
            "table.columns[].type",
            "table.columns[].nullable",
            "table.columns[].is_primary_key",
            "table.columns[].sensitive",
            "table.columns[].sensitivity_category",
            "table.foreign_keys[]",
            "table.indexes[]",
        ],
        "never_sent": [
            "registros/linhas",
            "valores de coluna",
            "valores padrão (defaults)",
            "senhas, tokens, chaves ou hashes",
            "tabelas do armazenamento interno do GenomAI",
        ],
        "sensitive_categories": [category.value for category in SensitivityCategory],
        "mask_sensitive_identifiers": settings.privacy_mask_sensitive_identifiers,
        "redact_digit_runs": settings.privacy_redact_digit_runs,
        "excluded_tables": sorted(settings.analysis_exclusion_set),
        "audit": "SHA-256 do payload é registrado; o conteúdo não é armazenado.",
    }
