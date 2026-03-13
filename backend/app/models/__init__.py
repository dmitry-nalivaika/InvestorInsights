# filepath: backend/app/models/__init__.py
"""
SQLAlchemy ORM models — re-exports for convenience.

Importing this package registers all models with Base.metadata,
which is required for Alembic autogenerate and relationship resolution.
"""

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin
from app.models.chunk import DocumentChunk
from app.models.company import Company
from app.models.criterion import AnalysisCriterion, ComparisonOp, CriteriaCategory
from app.models.document import DocStatus, DocType, Document
from app.models.financial import FinancialStatement
from app.models.message import ChatMessage
from app.models.profile import AnalysisProfile
from app.models.result import AnalysisResult
from app.models.section import DocumentSection
from app.models.session import ChatSession

__all__ = [
    # Base & mixins
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "CreatedAtMixin",
    # Enums
    "DocType",
    "DocStatus",
    "CriteriaCategory",
    "ComparisonOp",
    # Models
    "Company",
    "Document",
    "DocumentSection",
    "DocumentChunk",
    "FinancialStatement",
    "AnalysisProfile",
    "AnalysisCriterion",
    "AnalysisResult",
    "ChatSession",
    "ChatMessage",
]
