from enum import Enum

from pydantic import BaseModel, Field, field_validator

class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    ERROR = "error"

class Citation(BaseModel):
    doc_id: str = Field(description="Source document id, e.g. SAF-003")
    clause_id: str = Field(description="Exact clause id, e.g. SAF-003-C7")
    doc_title: str = ""
    section: str = ""
    quote: str = Field(default="", description="Short verbatim extract from the clause")

    @property
    def label(self):
        return f"{self.doc_id} {self.clause_id}"

class GroundedAnswer(BaseModel):
    answer: str = Field(description="Answer grounded only in the retrieved clauses")
    status: AnswerStatus = AnswerStatus.ANSWERED
    citations: list[Citation] = Field(default_factory=list)

    applicable_guideline: str = Field(default="", description="Guideline that governs this, with its clause id")
    requirement: str = Field(default="", description="What the seller must do, as an obligation")
    labeling_safety_condition: str = Field(default="", description="Labeling or safety condition, or 'None'")

    grounding_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = Field(default="", description="One sentence on whether the clauses support the answer")

    @field_validator("grounding_confidence", mode="before")
    @classmethod
    def normalise_confidence(cls, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if value > 1.0:
            value = value / 100.0
        return max(0.0, min(1.0, value))

    @property
    def abstained(self):
        return self.status == AnswerStatus.ABSTAINED

    @property
    def errored(self):
        return self.status == AnswerStatus.ERROR

    @property
    def citation_labels(self):
        return [c.label for c in self.citations]

class RetrievedChunk(BaseModel):
    citation: str
    clause_id: str
    clause_title: str = ""
    doc_type: str = ""
    text: str = ""
    rrf_score: float = 0.0
    rerank_score: float | None = None

class AssistantResponse(BaseModel):
    question: str
    rewritten_query: str = ""
    sub_queries: list[str] = Field(default_factory=list)
    answer: GroundedAnswer
    retrieved: list[RetrievedChunk] = Field(default_factory=list)
    model: str = ""
    latency_seconds: float = 0.0
