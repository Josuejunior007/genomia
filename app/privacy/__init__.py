"""Camada de privacidade do GenomAI (metadados seguros para IA)."""

from app.privacy.metadata import (
    SAFE_METADATA_POLICY,
    SafeAiPayload,
    SafeSchemaContext,
    assert_safe_payload,
    build_safe_schema_context,
    classify_sensitive,
    privacy_policy_payload,
    sanitize_deterministic_report,
    sanitize_identifier,
)

__all__ = [
    "SAFE_METADATA_POLICY",
    "SafeAiPayload",
    "SafeSchemaContext",
    "assert_safe_payload",
    "build_safe_schema_context",
    "classify_sensitive",
    "privacy_policy_payload",
    "sanitize_deterministic_report",
    "sanitize_identifier",
]
