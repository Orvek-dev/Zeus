from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


OntologyProvenanceSource = str


class OntologyProvenanceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    source_id: str
    source_type: OntologyProvenanceSource

    @field_validator("source_id", "source_type")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("{0} must be non-empty".format(info.field_name))
        return normalized

    @property
    def is_research_or_evidence(self) -> bool:
        return self.source_type in {"research", "evidence"}
