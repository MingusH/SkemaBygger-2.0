from pydantic import BaseModel
from typing import Literal


class ValidationIssue(BaseModel):
    rule: str                          # "V1", "W1", etc.
    level: Literal["error", "warning"]
    message: str
    entity_type: str | None = None
    entity_id: int | None = None


class ValidationResult(BaseModel):
    school_id: int
    is_valid: bool                     # False if any errors (not warnings) present
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
