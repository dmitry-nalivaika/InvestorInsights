"""T010 validation script — delete after use."""
import uuid
from datetime import datetime, date
from decimal import Decimal

from app.schemas.common import (
    AppBaseModel, PaginationParams, PaginatedResponse,
    ErrorDetail, ErrorResponse, TaskProgress, TaskStatusResponse,
    HealthComponent, HealthResponse,
)
from app.schemas.company import (
    CompanyCreate, CompanyUpdate, CompanyRead, CompanyListItem,
    CompanyList, CompanyDetail, DocumentsSummary, FinancialsSummary,
)
from app.schemas.document import (
    DocumentUpload, FetchSECRequest, DocumentRead, DocumentDetail,
    DocumentList, DocumentUploadResponse, FetchSECResponse, SectionSummary,
)
from app.schemas.chat import (
    ChatRequest, RetrievalConfig, ChatMessageRead, ChatSessionRead,
    ChatSessionDetail, ChatSessionList,
    SSESessionEvent, SSESourcesEvent, SSETokenEvent, SSEDoneEvent, SSEErrorEvent,
)
from app.schemas.analysis import (
    CriterionDef, CriterionRead, ProfileCreate, ProfileUpdate,
    ProfileRead, ProfileDetail, ProfileList,
    AnalysisRunRequest, CriteriaResultItem, AnalysisResultRead,
    AnalysisRunResponse, AnalysisResultList,
    FormulaInfo, FormulaListResponse,
)
from app.schemas.financial import (
    FinancialPeriod, FinancialsResponse, FinancialExportMeta,
)

print("1. All schema modules imported OK")

company = CompanyRead(
    id=uuid.uuid4(), ticker="AAPL", name="Apple Inc.",
    created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
)
d = company.model_dump()
assert d["ticker"] == "AAPL"
print("2. CompanyRead serialize OK")

c = CompanyCreate(ticker="  aapl  ")
assert c.ticker == "AAPL"
print("3. CompanyCreate ticker->AAPL validator OK")

doc = DocumentUpload(
    doc_type="10-K", fiscal_year=2024,
    filing_date=date(2024, 10, 31), period_end_date=date(2024, 9, 28),
)
assert doc.doc_type.value == "10-K"
print("4. DocumentUpload OK")

chat = ChatRequest(message="What are the key risk factors?")
assert len(chat.message) > 0
print("5. ChatRequest OK")

profile = ProfileCreate(
    name="Value Investing",
    criteria=[CriterionDef(
        name="Net Margin", category="profitability",
        formula="net_margin", comparison=">=", threshold_value=Decimal("0.15"),
    )],
)
assert len(profile.criteria) == 1
print("6. ProfileCreate+CriterionDef OK")

result = AnalysisResultRead(
    id=uuid.uuid4(), company_id=uuid.uuid4(), profile_id=uuid.uuid4(),
    profile_version=1, run_at=datetime.utcnow(),
    overall_score=Decimal("8.5"), max_score=Decimal("10"),
    pct_score=Decimal("85.00"), grade="B",
    created_at=datetime.utcnow(),
)
assert result.grade == "B"
print("7. AnalysisResultRead OK")

fp = FinancialPeriod(
    fiscal_year=2024, period_end_date=date(2024, 9, 28),
    income_statement={"revenue": 394328000000},
    balance_sheet={"total_assets": 352583000000},
    cash_flow={"operating_cash_flow": 110543000000},
)
assert fp.fiscal_year == 2024
print("8. FinancialPeriod OK")

health = HealthResponse(
    status="healthy", version="1.0.0", uptime_seconds=3600,
    components={"database": HealthComponent(status="healthy", latency_ms=2.5)},
)
assert health.status == "healthy"
print("9. HealthResponse OK")

err = ErrorResponse(status=404, error="not_found", message="Company not found")
assert err.status == 404
print("10. ErrorResponse OK")

pl = CompanyList(items=[], total=0, limit=50, offset=0)
assert pl.total == 0
print("11. PaginatedResponse[CompanyListItem] OK")

sse = SSETokenEvent(token="Hello")
assert sse.token == "Hello"
done = SSEDoneEvent(message_id=uuid.uuid4(), token_count=523)
print("12. SSE event schemas OK")


class FakeORM:
    id = uuid.uuid4()
    ticker = "MSFT"
    name = "Microsoft Corporation"
    cik = None
    sector = "Technology"
    industry = None
    description = None
    metadata_ = {}
    created_at = datetime.utcnow()
    updated_at = datetime.utcnow()


orm_company = CompanyRead.model_validate(FakeORM())
assert orm_company.ticker == "MSFT"
print("13. from_attributes (ORM mode) OK")

from pydantic import BaseModel
import app.schemas.common as _c
import app.schemas.company as _co
import app.schemas.document as _d
import app.schemas.chat as _ch
import app.schemas.analysis as _a
import app.schemas.financial as _f

total = 0
for mod in [_c, _co, _d, _ch, _a, _f]:
    count = sum(1 for name in dir(mod)
                if not name.startswith("_")
                and isinstance(getattr(mod, name, None), type)
                and issubclass(getattr(mod, name), BaseModel)
                and getattr(mod, name) is not BaseModel
                and getattr(mod, name) is not AppBaseModel)
    total += count
print(f"\nTotal Pydantic schema classes: {total}")
print("\nAll T010 schemas validated successfully!")
