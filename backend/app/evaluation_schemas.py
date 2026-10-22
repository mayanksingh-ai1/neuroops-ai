"""Explicit, bounded input contracts shared by JSON and CSV ingestion."""
import json
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MetricName = Literal['correctness', 'relevance', 'instruction_following', 'groundedness', 'citation_validity', 'safety']
ChunkId = Annotated[str, Field(pattern=r'^[a-f0-9-]{36}$')]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)


class Rules(Strict):
    max_words: int | None = Field(default=None, ge=1, le=2000)
    required_terms: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(default_factory=list, max_length=10)
    json_object: bool = False
    require_citations: bool = False


class Citation(Strict):
    chunk_id: ChunkId
    quote: str = Field(min_length=1, max_length=2000)


class CaseInput(Strict):
    dataset: str = Field(default='default', min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    provider: str = Field(default='supplied', min_length=1, max_length=80)
    question: str = Field(min_length=3, max_length=2000)
    response: str = Field(min_length=1, max_length=8000)
    reference: str | None = Field(default=None, min_length=1, max_length=8000)
    instructions: str = Field(default='', max_length=2000)
    policy: str = Field(default='', max_length=2000)
    evidence_chunk_ids: list[ChunkId] = Field(default_factory=list, max_length=5)
    citations: list[Citation] = Field(default_factory=list, max_length=10)
    rules: Rules = Field(default_factory=Rules)
    metadata: dict[Annotated[str, Field(min_length=1, max_length=80)], Annotated[str, Field(max_length=500)]] = Field(default_factory=dict, max_length=20)

    @field_validator('evidence_chunk_ids')
    @classmethod
    def unique_ids(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Evidence chunk IDs must be distinct.')
        return value

    @model_validator(mode='after')
    def bounded_text(self):
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for key, item in value.items():
                    yield str(key)
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
        if any(ord(c) < 32 and c not in '\n\r\t' for text in strings(self.model_dump()) for c in text):
            raise ValueError('Unsupported control character.')
        if len(json.dumps(self.model_dump(), ensure_ascii=False).encode('utf-8')) > 48000:
            raise ValueError('Case exceeds the 48,000-byte limit.')
        ids = [citation.chunk_id for citation in self.citations]
        if len(ids) != len(set(ids)):
            raise ValueError('Use one citation quote per chunk ID.')
        return self


class EvaluateInput(Strict):
    use_judge: bool = False
    provider_consent: bool = False


class ComparisonInput(EvaluateInput):
    case_ids: list[ChunkId] = Field(min_length=2, max_length=4)

    @model_validator(mode='after')
    def valid_comparison(self):
        if len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError('Choose distinct cases.')
        if self.use_judge and len(self.case_ids) != 2:
            raise ValueError('Pairwise judging requires exactly two responses.')
        return self


class Correction(Strict):
    score: float | None = Field(ge=0, le=1, allow_inf_nan=False)
    reason: str = Field(min_length=3, max_length=1000)


class ReviewInput(Strict):
    decision: Literal['approve', 'reject', 'correct']
    feedback: str = Field(min_length=3, max_length=2000)
    corrections: dict[MetricName, Correction] = Field(default_factory=dict, max_length=6)

    @model_validator(mode='after')
    def correction_required(self):
        if (self.decision == 'correct') != bool(self.corrections):
            raise ValueError('Only correct decisions require metric corrections.')
        return self
