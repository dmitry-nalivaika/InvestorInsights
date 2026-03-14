# filepath: backend/tests/unit/test_request_validation.py
"""Unit tests for request validation hardening (T812).

Covers:
  - CompanyUpdate.description max_length
  - AnalysisRunRequest duplicate company_ids
  - ComparisonRequest duplicate company_ids
  - ProfileCreate / ProfileUpdate name stripping, blank rejection, max_length
  - ProfileCreate / ProfileUpdate description max_length
  - FetchSECRequest filing_types validation (invalid types, min/max length)
"""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("API_KEY", "test-validation-unit")

import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    AnalysisRunRequest,
    ComparisonRequest,
    ProfileCreate,
    ProfileUpdate,
)
from app.schemas.company import CompanyUpdate
from app.schemas.document import FetchSECRequest

# ── Helpers ──────────────────────────────────────────────────────

def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _minimal_criterion(**overrides) -> dict:
    """Return a minimal valid CriterionDef dict."""
    base = {
        "name": "ROE",
        "category": "profitability",
        "formula": "net_income / equity",
        "comparison": ">=",
        "threshold_value": "0.15",
    }
    base.update(overrides)
    return base


# =====================================================================
# CompanyUpdate.description
# =====================================================================

class TestCompanyUpdateDescription:
    """CompanyUpdate.description must be <= 5000 chars."""

    def test_description_within_limit(self) -> None:
        update = CompanyUpdate(description="A" * 5000)
        assert len(update.description) == 5000

    def test_description_exceeds_limit(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            CompanyUpdate(description="A" * 5001)
        errors = exc_info.value.errors()
        assert any("5000" in str(e) for e in errors)

    def test_description_none_allowed(self) -> None:
        update = CompanyUpdate(description=None)
        assert update.description is None

    def test_description_empty_string(self) -> None:
        # AppBaseModel has str_strip_whitespace; empty is fine for optional
        update = CompanyUpdate(description="")
        assert update.description is not None  # empty string, not None


# =====================================================================
# AnalysisRunRequest — duplicate company_ids
# =====================================================================

class TestAnalysisRunRequestDuplicates:
    """AnalysisRunRequest rejects duplicate company_ids."""

    def test_unique_ids_pass(self) -> None:
        ids = [_uid(), _uid()]
        req = AnalysisRunRequest(company_ids=ids, profile_id=_uid())
        assert len(req.company_ids) == 2

    def test_single_id_passes(self) -> None:
        req = AnalysisRunRequest(company_ids=[_uid()], profile_id=_uid())
        assert len(req.company_ids) == 1

    def test_duplicate_ids_rejected(self) -> None:
        dup = _uid()
        with pytest.raises(ValidationError) as exc_info:
            AnalysisRunRequest(company_ids=[dup, dup], profile_id=_uid())
        errors = exc_info.value.errors()
        assert any("duplicate" in str(e).lower() for e in errors)

    def test_duplicate_among_many(self) -> None:
        dup = _uid()
        with pytest.raises(ValidationError) as exc_info:
            AnalysisRunRequest(
                company_ids=[_uid(), dup, _uid(), dup],
                profile_id=_uid(),
            )
        assert "duplicate" in str(exc_info.value).lower()

    def test_empty_list_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisRunRequest(company_ids=[], profile_id=_uid())

    def test_exceeds_max_length(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisRunRequest(company_ids=[_uid() for _ in range(11)], profile_id=_uid())


# =====================================================================
# ComparisonRequest — duplicate company_ids
# =====================================================================

class TestComparisonRequestDuplicates:
    """ComparisonRequest rejects duplicate company_ids (min_length=2)."""

    def test_two_unique_ids_pass(self) -> None:
        req = ComparisonRequest(company_ids=[_uid(), _uid()], profile_id=_uid())
        assert len(req.company_ids) == 2

    def test_duplicate_ids_rejected(self) -> None:
        dup = _uid()
        with pytest.raises(ValidationError) as exc_info:
            ComparisonRequest(company_ids=[dup, dup], profile_id=_uid())
        assert "duplicate" in str(exc_info.value).lower()

    def test_single_id_rejected_min_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonRequest(company_ids=[_uid()], profile_id=_uid())

    def test_exceeds_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ComparisonRequest(company_ids=[_uid() for _ in range(11)], profile_id=_uid())


# =====================================================================
# ProfileCreate — name validation
# =====================================================================

class TestProfileCreateName:
    """ProfileCreate.name must be 1-100 chars, stripped, non-blank."""

    def test_valid_name(self) -> None:
        p = ProfileCreate(
            name="My Profile",
            criteria=[_minimal_criterion()],
        )
        assert p.name == "My Profile"

    def test_name_is_stripped(self) -> None:
        p = ProfileCreate(
            name="  Padded Name  ",
            criteria=[_minimal_criterion()],
        )
        assert p.name == "Padded Name"

    def test_blank_name_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ProfileCreate(
                name="   ",
                criteria=[_minimal_criterion()],
            )
        err = str(exc_info.value).lower()
        # Either the min_length constraint or the custom validator message
        assert "blank" in err or "at least 1 character" in err

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProfileCreate(
                name="",
                criteria=[_minimal_criterion()],
            )

    def test_name_exceeds_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ProfileCreate(
                name="A" * 101,
                criteria=[_minimal_criterion()],
            )

    def test_name_at_max_length(self) -> None:
        p = ProfileCreate(
            name="A" * 100,
            criteria=[_minimal_criterion()],
        )
        assert len(p.name) == 100


# =====================================================================
# ProfileCreate — description max_length
# =====================================================================

class TestProfileCreateDescription:
    """ProfileCreate.description must be <= 1000 chars."""

    def test_description_within_limit(self) -> None:
        p = ProfileCreate(
            name="Test",
            description="D" * 1000,
            criteria=[_minimal_criterion()],
        )
        assert len(p.description) == 1000

    def test_description_exceeds_limit(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ProfileCreate(
                name="Test",
                description="D" * 1001,
                criteria=[_minimal_criterion()],
            )
        assert any("1000" in str(e) for e in exc_info.value.errors())

    def test_description_none_allowed(self) -> None:
        p = ProfileCreate(
            name="Test",
            description=None,
            criteria=[_minimal_criterion()],
        )
        assert p.description is None


# =====================================================================
# ProfileCreate — criteria bounds
# =====================================================================

class TestProfileCreateCriteria:
    """ProfileCreate.criteria must have 1..30 items."""

    def test_empty_criteria_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProfileCreate(name="Test", criteria=[])

    def test_exceeds_max_criteria(self) -> None:
        with pytest.raises(ValidationError):
            ProfileCreate(
                name="Test",
                criteria=[_minimal_criterion(name=f"C{i}") for i in range(31)],
            )

    def test_max_criteria_accepted(self) -> None:
        p = ProfileCreate(
            name="Test",
            criteria=[_minimal_criterion(name=f"C{i}") for i in range(30)],
        )
        assert len(p.criteria) == 30


# =====================================================================
# ProfileUpdate — name validation
# =====================================================================

class TestProfileUpdateName:
    """ProfileUpdate.name is optional but validated when provided."""

    def test_none_name_allowed(self) -> None:
        p = ProfileUpdate(name=None)
        assert p.name is None

    def test_valid_name(self) -> None:
        p = ProfileUpdate(name="Updated")
        assert p.name == "Updated"

    def test_name_is_stripped(self) -> None:
        p = ProfileUpdate(name="  Padded  ")
        assert p.name == "Padded"

    def test_blank_name_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ProfileUpdate(name="   ")
        err = str(exc_info.value).lower()
        assert "blank" in err or "at least 1 character" in err

    def test_name_exceeds_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ProfileUpdate(name="A" * 101)

    def test_description_exceeds_limit(self) -> None:
        with pytest.raises(ValidationError):
            ProfileUpdate(description="D" * 1001)


# =====================================================================
# FetchSECRequest — filing_types validation
# =====================================================================

class TestFetchSECRequestFilingTypes:
    """FetchSECRequest.filing_types validated against allowlist."""

    def test_default_filing_types(self) -> None:
        req = FetchSECRequest()
        assert req.filing_types == ["10-K", "10-Q"]

    def test_valid_single_type(self) -> None:
        req = FetchSECRequest(filing_types=["10-K"])
        assert req.filing_types == ["10-K"]

    def test_all_valid_types(self) -> None:
        req = FetchSECRequest(filing_types=["10-K", "10-Q", "8-K", "20-F", "DEF14A"])
        assert len(req.filing_types) == 5

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            FetchSECRequest(filing_types=["10-K", "FAKE-TYPE"])
        assert "FAKE-TYPE" in str(exc_info.value)

    def test_multiple_invalid_types(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            FetchSECRequest(filing_types=["NOPE", "ALSO-BAD"])
        err_str = str(exc_info.value)
        assert "NOPE" in err_str
        assert "ALSO-BAD" in err_str

    def test_empty_list_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FetchSECRequest(filing_types=[])

    def test_exceeds_max_filing_types(self) -> None:
        with pytest.raises(ValidationError):
            FetchSECRequest(filing_types=["10-K"] * 11)

    def test_years_back_range(self) -> None:
        # Valid bounds
        req_low = FetchSECRequest(years_back=1)
        assert req_low.years_back == 1
        req_high = FetchSECRequest(years_back=30)
        assert req_high.years_back == 30

    def test_years_back_below_min(self) -> None:
        with pytest.raises(ValidationError):
            FetchSECRequest(years_back=0)

    def test_years_back_above_max(self) -> None:
        with pytest.raises(ValidationError):
            FetchSECRequest(years_back=31)

    def test_case_sensitive_filing_types(self) -> None:
        """Filing types must match exact case (e.g. '10-k' is invalid)."""
        with pytest.raises(ValidationError) as exc_info:
            FetchSECRequest(filing_types=["10-k"])
        assert "10-k" in str(exc_info.value)


# =====================================================================
# CompanyCreate — ticker validation (existing, sanity check)
# =====================================================================

class TestCompanyCreateTicker:
    """CompanyCreate.ticker is uppercased and stripped."""

    def test_ticker_uppercased(self) -> None:
        from app.schemas.company import CompanyCreate

        c = CompanyCreate(ticker="aapl")
        assert c.ticker == "AAPL"

    def test_ticker_stripped(self) -> None:
        from app.schemas.company import CompanyCreate

        c = CompanyCreate(ticker="  msft  ")
        assert c.ticker == "MSFT"

    def test_ticker_max_length(self) -> None:
        from app.schemas.company import CompanyCreate

        with pytest.raises(ValidationError):
            CompanyCreate(ticker="A" * 11)

    def test_ticker_empty_rejected(self) -> None:
        from app.schemas.company import CompanyCreate

        with pytest.raises(ValidationError):
            CompanyCreate(ticker="")
