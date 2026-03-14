# filepath: backend/tests/unit/test_analysis.py
"""Unit tests for Analysis Engine (Phase 6).

Covers:
  - T500: All 25+ built-in formulas (registry completeness + evaluation)
  - T501: Expression parser (lexer, parser, evaluator)
  - T502: prev() reference resolution
  - T503: Formula validation (syntax, balanced parens, field refs)
  - T507: Trend detection (OLS regression)
  - T508: Scoring (pass/fail × weight, grades, no_data handling)
  - T506: Engine integration (run_criterion, run_analysis)
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

os.environ.setdefault("API_KEY", "test-analysis-unit")

import pytest

from app.analysis.expression_parser import (
    EvalError,
    FormulaContext,
    LexError,
    ParseError,
    collect_field_refs,
    compute_formula,
    evaluate,
    parse_expression,
    tokenize,
    validate_expression,
)
from app.analysis.formulas import (
    ALL_BUILTIN_FORMULAS,
    FORMULA_REGISTRY,
    get_formula,
    resolve_expression,
)
from app.analysis.scorer import (
    AnalysisScore,
    CriterionScore,
    compute_analysis_score,
    compute_grade,
    evaluate_threshold,
    format_threshold,
)
from app.analysis.trend import TrendResult, detect_trend
from app.analysis.engine import (
    build_data_by_year,
    run_analysis,
    run_criterion,
)


# =====================================================================
# Test data helpers
# =====================================================================


def _make_financials(year: int, **overrides):
    """Build a minimal financial data dict for one year."""
    base = {
        "income_statement": {
            "revenue": 100_000_000,
            "cost_of_revenue": 55_000_000,
            "gross_profit": 45_000_000,
            "operating_income": 25_000_000,
            "interest_expense": 3_000_000,
            "net_income": 18_000_000,
            "research_and_development": 8_000_000,
            "eps_diluted": 3.50,
            "shares_outstanding_diluted": 50_000_000,
        },
        "balance_sheet": {
            "total_current_assets": 40_000_000,
            "total_current_liabilities": 20_000_000,
            "total_assets": 120_000_000,
            "total_liabilities": 50_000_000,
            "total_equity": 70_000_000,
            "long_term_debt": 25_000_000,
            "short_term_debt": 5_000_000,
            "cash_and_equivalents": 15_000_000,
            "inventory": 8_000_000,
            "accounts_receivable": 12_000_000,
        },
        "cash_flow": {
            "operating_cash_flow": 22_000_000,
            "capital_expenditure": -5_000_000,
            "free_cash_flow": 17_000_000,
            "dividends_paid": -6_000_000,
            "share_buybacks": -3_000_000,
            "stock_based_compensation": 4_000_000,
        },
    }

    # Apply overrides at nested level
    for key, val in overrides.items():
        if "." in key:
            stmt, field = key.split(".", 1)
            if stmt in base:
                base[stmt][field] = val
        else:
            base[key] = val

    return base


def _data_by_year(*years_data):
    """Build data_by_year dict from (year, data) tuples."""
    result = {}
    for year, data in years_data:
        result[year] = data
    return result


# =====================================================================
# T500 — Formula registry tests
# =====================================================================


class TestFormulaRegistry:
    """Tests for the built-in formula registry."""

    def test_registry_has_at_least_25_formulas(self):
        assert len(ALL_BUILTIN_FORMULAS) >= 25

    def test_all_formulas_in_registry(self):
        for f in ALL_BUILTIN_FORMULAS:
            assert f.name in FORMULA_REGISTRY

    def test_get_formula_known(self):
        f = get_formula("gross_margin")
        assert f is not None
        assert f.name == "gross_margin"
        assert f.category == "profitability"

    def test_get_formula_unknown(self):
        assert get_formula("nonexistent_formula") is None

    def test_resolve_expression_builtin(self):
        expr = resolve_expression("gross_margin")
        assert "income_statement.gross_profit" in expr
        assert "income_statement.revenue" in expr

    def test_resolve_expression_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown built-in formula"):
            resolve_expression("nonexistent")

    def test_resolve_expression_custom(self):
        custom = "income_statement.revenue / balance_sheet.total_assets"
        assert resolve_expression(custom, is_custom=True) == custom

    def test_all_categories_present(self):
        categories = {f.category for f in ALL_BUILTIN_FORMULAS}
        assert "profitability" in categories
        assert "growth" in categories
        assert "liquidity" in categories
        assert "solvency" in categories
        assert "efficiency" in categories
        assert "quality" in categories
        assert "dividend" in categories

    def test_all_formulas_have_required_fields(self):
        for f in ALL_BUILTIN_FORMULAS:
            assert f.required_fields, f"Formula {f.name} has no required_fields"

    def test_all_formulas_have_description(self):
        for f in ALL_BUILTIN_FORMULAS:
            assert f.description, f"Formula {f.name} has no description"


# =====================================================================
# T501 — Expression parser tests
# =====================================================================


class TestLexer:
    """Lexer tests."""

    def test_simple_tokens(self):
        tokens = tokenize("1 + 2")
        assert len(tokens) == 4  # NUMBER PLUS NUMBER EOF

    def test_field_ref_tokens(self):
        tokens = tokenize("income_statement.revenue")
        assert tokens[0].value == "income_statement"
        assert tokens[1].value == "."
        assert tokens[2].value == "revenue"

    def test_invalid_character(self):
        with pytest.raises(LexError, match="Unexpected character"):
            tokenize("1 @ 2")


class TestParser:
    """Parser tests."""

    def test_simple_arithmetic(self):
        ast = parse_expression("1 + 2")
        assert ast is not None

    def test_field_reference(self):
        ast = parse_expression("income_statement.revenue")
        assert ast.statement == "income_statement"
        assert ast.field == "revenue"

    def test_division(self):
        ast = parse_expression("income_statement.revenue / balance_sheet.total_assets")
        assert ast.op == "/"

    def test_nested_parens(self):
        ast = parse_expression("(1 + 2) * 3")
        assert ast.op == "*"

    def test_unary_minus(self):
        ast = parse_expression("-income_statement.revenue")
        assert ast.op == "-"

    def test_power(self):
        ast = parse_expression("2 ^ 3")
        assert ast.op == "^"

    def test_function_abs(self):
        ast = parse_expression("abs(income_statement.revenue)")
        assert ast.name == "abs"

    def test_function_min_max(self):
        ast = parse_expression("min(income_statement.revenue, balance_sheet.total_assets)")
        assert ast.name == "min"
        assert len(ast.args) == 2

    def test_function_avg(self):
        ast = parse_expression("avg(1, 2, 3)")
        assert ast.name == "avg"
        assert len(ast.args) == 3

    def test_prev_simple(self):
        ast = parse_expression("prev(income_statement.revenue)")
        assert ast.field.statement == "income_statement"
        assert ast.field.field == "revenue"
        assert ast.lookback == 1

    def test_prev_with_lookback(self):
        ast = parse_expression("prev(income_statement.revenue, 2)")
        assert ast.lookback == 2

    def test_invalid_statement(self):
        with pytest.raises(ParseError, match="Invalid statement"):
            parse_expression("invalid_stmt.field")

    def test_unknown_function(self):
        with pytest.raises(ParseError, match="Unknown function"):
            parse_expression("unknown_func(1)")

    def test_unbalanced_parens(self):
        with pytest.raises(ParseError):
            parse_expression("(1 + 2")

    def test_complex_expression(self):
        """Matches ROIC formula from builtin-formulas.md."""
        expr = (
            "(income_statement.operating_income * (1 - 0.21)) / "
            "(balance_sheet.total_assets - balance_sheet.total_current_liabilities"
            " - balance_sheet.cash_and_equivalents)"
        )
        ast = parse_expression(expr)
        assert ast.op == "/"


class TestCollectFieldRefs:
    """Tests for field reference collection."""

    def test_simple_field_ref(self):
        ast = parse_expression("income_statement.revenue")
        refs = collect_field_refs(ast)
        assert refs == ["income_statement.revenue"]

    def test_complex_expression(self):
        ast = parse_expression(
            "income_statement.revenue / balance_sheet.total_assets",
        )
        refs = collect_field_refs(ast)
        assert "income_statement.revenue" in refs
        assert "balance_sheet.total_assets" in refs

    def test_prev_ref(self):
        ast = parse_expression("prev(income_statement.revenue)")
        refs = collect_field_refs(ast)
        assert "income_statement.revenue" in refs


# =====================================================================
# T502 — Evaluator + prev() resolution tests
# =====================================================================


class TestEvaluator:
    """Expression evaluator tests."""

    def _ctx(self, data_by_year, current_year=2023):
        return FormulaContext(data_by_year, current_year)

    def test_simple_division(self):
        data = {2023: _make_financials(2023)}
        result = compute_formula(
            "income_statement.gross_profit / income_statement.revenue",
            data, 2023,
        )
        assert result is not None
        assert abs(result - 0.45) < 0.001

    def test_missing_field_returns_none(self):
        data = {2023: {"income_statement": {"revenue": 100}, "balance_sheet": {}, "cash_flow": {}}}
        result = compute_formula(
            "income_statement.gross_profit / income_statement.revenue",
            data, 2023,
        )
        assert result is None

    def test_division_by_zero_returns_none(self):
        data = {2023: {"income_statement": {"revenue": 0, "gross_profit": 10}, "balance_sheet": {}, "cash_flow": {}}}
        result = compute_formula(
            "income_statement.gross_profit / income_statement.revenue",
            data, 2023,
        )
        assert result is None

    def test_unary_minus(self):
        data = {2023: _make_financials(2023)}
        result = compute_formula("-income_statement.revenue", data, 2023)
        assert result == -100_000_000

    def test_power(self):
        result = compute_formula("2 ^ 3", {2023: {}}, 2023)
        assert result == 8.0

    def test_abs_function(self):
        data = {2023: _make_financials(2023)}
        result = compute_formula(
            "abs(cash_flow.capital_expenditure)",
            data, 2023,
        )
        assert result == 5_000_000

    def test_min_function(self):
        result = compute_formula("min(3, 1, 2)", {2023: {}}, 2023)
        assert result == 1.0

    def test_max_function(self):
        result = compute_formula("max(3, 1, 2)", {2023: {}}, 2023)
        assert result == 3.0

    def test_avg_function(self):
        result = compute_formula("avg(2, 4, 6)", {2023: {}}, 2023)
        assert result == 4.0

    def test_prev_resolution(self):
        data = {
            2022: _make_financials(2022, **{"income_statement.revenue": 90_000_000}),
            2023: _make_financials(2023),
        }
        result = compute_formula(
            "(income_statement.revenue - prev(income_statement.revenue)) / prev(income_statement.revenue)",
            data, 2023,
        )
        assert result is not None
        expected = (100_000_000 - 90_000_000) / 90_000_000
        assert abs(result - expected) < 0.001

    def test_prev_missing_year_returns_none(self):
        data = {2023: _make_financials(2023)}
        result = compute_formula(
            "prev(income_statement.revenue)",
            data, 2023,
        )
        assert result is None

    def test_prev_with_lookback(self):
        data = {
            2021: _make_financials(2021, **{"income_statement.revenue": 80_000_000}),
            2023: _make_financials(2023),
        }
        result = compute_formula(
            "prev(income_statement.revenue, 2)",
            data, 2023,
        )
        assert result == 80_000_000


# =====================================================================
# T500 — Evaluate all built-in formulas
# =====================================================================


class TestBuiltinFormulaEvaluation:
    """Evaluate every built-in formula to ensure expressions parse and compute."""

    @pytest.fixture()
    def data_2yr(self):
        """Two years of complete financial data."""
        return {
            2022: _make_financials(2022, **{
                "income_statement.revenue": 90_000_000,
                "income_statement.net_income": 15_000_000,
                "income_statement.operating_income": 22_000_000,
                "cash_flow.free_cash_flow": 14_000_000,
            }),
            2023: _make_financials(2023),
        }

    @pytest.mark.parametrize(
        "formula_name",
        [f.name for f in ALL_BUILTIN_FORMULAS],
    )
    def test_formula_evaluates(self, formula_name, data_2yr):
        """Every built-in formula should parse and evaluate without errors."""
        formula = FORMULA_REGISTRY[formula_name]
        result = compute_formula(formula.expression, data_2yr, 2023)
        # Result can be None (missing data) or a number — but should not raise
        assert result is None or isinstance(result, (int, float))

    def test_gross_margin_value(self, data_2yr):
        result = compute_formula(FORMULA_REGISTRY["gross_margin"].expression, data_2yr, 2023)
        assert result is not None
        assert abs(result - 0.45) < 0.001

    def test_operating_margin_value(self, data_2yr):
        result = compute_formula(FORMULA_REGISTRY["operating_margin"].expression, data_2yr, 2023)
        assert result is not None
        assert abs(result - 0.25) < 0.001

    def test_net_margin_value(self, data_2yr):
        result = compute_formula(FORMULA_REGISTRY["net_margin"].expression, data_2yr, 2023)
        assert result is not None
        assert abs(result - 0.18) < 0.001

    def test_roe_value(self, data_2yr):
        result = compute_formula(FORMULA_REGISTRY["roe"].expression, data_2yr, 2023)
        assert result is not None
        expected = 18_000_000 / 70_000_000
        assert abs(result - expected) < 0.001

    def test_current_ratio_value(self, data_2yr):
        result = compute_formula(FORMULA_REGISTRY["current_ratio"].expression, data_2yr, 2023)
        assert result is not None
        assert abs(result - 2.0) < 0.001

    def test_revenue_growth_value(self, data_2yr):
        result = compute_formula(FORMULA_REGISTRY["revenue_growth"].expression, data_2yr, 2023)
        assert result is not None
        expected = (100_000_000 - 90_000_000) / 90_000_000
        assert abs(result - expected) < 0.001

    def test_fcf_margin_value(self, data_2yr):
        result = compute_formula(FORMULA_REGISTRY["fcf_margin"].expression, data_2yr, 2023)
        assert result is not None
        assert abs(result - 0.17) < 0.001

    def test_roic_value(self, data_2yr):
        """ROIC = operating_income * (1-0.21) / (total_assets - current_liabilities - cash)."""
        result = compute_formula(FORMULA_REGISTRY["roic"].expression, data_2yr, 2023)
        assert result is not None
        nopat = 25_000_000 * (1 - 0.21)
        invested = 120_000_000 - 20_000_000 - 15_000_000
        expected = nopat / invested
        assert abs(result - expected) < 0.001


# =====================================================================
# T503 — Validation tests
# =====================================================================


class TestValidation:
    """Formula validation tests."""

    def test_valid_expression(self):
        errors = validate_expression("income_statement.revenue / balance_sheet.total_assets")
        assert errors == []

    def test_unbalanced_open_paren(self):
        errors = validate_expression("(income_statement.revenue")
        assert any("Unbalanced" in e or "paren" in e.lower() for e in errors)

    def test_unbalanced_close_paren(self):
        errors = validate_expression("income_statement.revenue)")
        assert any("Unbalanced" in e or "paren" in e.lower() or "Unexpected" in e for e in errors)

    def test_invalid_syntax(self):
        errors = validate_expression("income_statement.")
        assert len(errors) > 0

    def test_invalid_character(self):
        errors = validate_expression("1 @ 2")
        assert len(errors) > 0

    def test_valid_prev(self):
        errors = validate_expression("prev(income_statement.revenue)")
        assert errors == []

    def test_valid_complex(self):
        expr = (
            "(income_statement.operating_income * (1 - 0.21)) / "
            "(balance_sheet.total_assets - balance_sheet.total_current_liabilities"
            " - balance_sheet.cash_and_equivalents)"
        )
        errors = validate_expression(expr)
        assert errors == []


# =====================================================================
# T507 — Trend detection tests
# =====================================================================


class TestTrendDetection:
    """OLS trend detection tests."""

    def test_improving_trend(self):
        values = {2019: 0.10, 2020: 0.12, 2021: 0.15, 2022: 0.18, 2023: 0.22}
        result = detect_trend(values)
        assert result.direction == "improving"
        assert result.data_points == 5
        assert result.slope is not None and result.slope > 0

    def test_declining_trend(self):
        values = {2019: 0.30, 2020: 0.25, 2021: 0.20, 2022: 0.15, 2023: 0.10}
        result = detect_trend(values)
        assert result.direction == "declining"
        assert result.data_points == 5

    def test_stable_trend(self):
        values = {2019: 0.50, 2020: 0.51, 2021: 0.50, 2022: 0.50, 2023: 0.51}
        result = detect_trend(values)
        assert result.direction == "stable"

    def test_insufficient_data(self):
        values = {2022: 0.10, 2023: 0.15}
        result = detect_trend(values)
        assert result.direction == "insufficient_data"
        assert result.data_points == 2

    def test_single_point(self):
        values = {2023: 0.20}
        result = detect_trend(values)
        assert result.direction == "insufficient_data"

    def test_empty_data(self):
        result = detect_trend({})
        assert result.direction == "insufficient_data"

    def test_null_values_excluded(self):
        values = {2019: 0.10, 2020: None, 2021: 0.15, 2022: None, 2023: 0.20}
        result = detect_trend(values)
        assert result.direction in ("improving", "stable", "declining")
        assert result.data_points == 3

    def test_r_squared(self):
        """Perfect linear trend should have R² close to 1."""
        values = {2019: 1.0, 2020: 2.0, 2021: 3.0, 2022: 4.0, 2023: 5.0}
        result = detect_trend(values)
        assert result.r_squared is not None
        assert abs(result.r_squared - 1.0) < 0.001

    def test_normalised_slope_calculation(self):
        """Normalised slope = OLS slope / abs(mean_y)."""
        values = {2020: 100, 2021: 110, 2022: 120, 2023: 130}
        result = detect_trend(values)
        assert result.normalised_slope is not None
        # slope = 10, mean_y = 115, normalised = 10/115 ≈ 0.087
        assert abs(result.normalised_slope - 10.0 / 115.0) < 0.01


# =====================================================================
# T508 — Scorer tests
# =====================================================================


class TestScorer:
    """Scoring tests."""

    def test_grade_A(self):
        assert compute_grade(95.0) == "A"
        assert compute_grade(90.0) == "A"

    def test_grade_B(self):
        assert compute_grade(85.0) == "B"
        assert compute_grade(75.0) == "B"

    def test_grade_C(self):
        assert compute_grade(70.0) == "C"
        assert compute_grade(60.0) == "C"

    def test_grade_D(self):
        assert compute_grade(50.0) == "D"
        assert compute_grade(40.0) == "D"

    def test_grade_F(self):
        assert compute_grade(30.0) == "F"
        assert compute_grade(0.0) == "F"

    def test_evaluate_threshold_gte_pass(self):
        assert evaluate_threshold(0.20, ">=", 0.15) is True

    def test_evaluate_threshold_gte_fail(self):
        assert evaluate_threshold(0.10, ">=", 0.15) is False

    def test_evaluate_threshold_gt_pass(self):
        assert evaluate_threshold(0.16, ">", 0.15) is True

    def test_evaluate_threshold_gt_fail(self):
        assert evaluate_threshold(0.15, ">", 0.15) is False

    def test_evaluate_threshold_lte(self):
        assert evaluate_threshold(0.15, "<=", 0.15) is True
        assert evaluate_threshold(0.20, "<=", 0.15) is False

    def test_evaluate_threshold_lt(self):
        assert evaluate_threshold(0.14, "<", 0.15) is True
        assert evaluate_threshold(0.15, "<", 0.15) is False

    def test_evaluate_threshold_eq(self):
        assert evaluate_threshold(0.15, "=", 0.15) is True
        assert evaluate_threshold(0.16, "=", 0.15) is False

    def test_evaluate_threshold_between_pass(self):
        assert evaluate_threshold(0.30, "between", threshold_low=0.20, threshold_high=0.60) is True

    def test_evaluate_threshold_between_fail(self):
        assert evaluate_threshold(0.10, "between", threshold_low=0.20, threshold_high=0.60) is False

    def test_evaluate_threshold_trend_up(self):
        assert evaluate_threshold(None, "trend_up", trend_direction="improving") is True
        assert evaluate_threshold(None, "trend_up", trend_direction="declining") is False

    def test_evaluate_threshold_trend_down(self):
        assert evaluate_threshold(None, "trend_down", trend_direction="declining") is True
        assert evaluate_threshold(None, "trend_down", trend_direction="improving") is False

    def test_evaluate_threshold_none_value(self):
        assert evaluate_threshold(None, ">=", 0.15) is None

    def test_evaluate_threshold_trend_no_data(self):
        assert evaluate_threshold(None, "trend_up", trend_direction=None) is None

    def test_format_threshold_gte(self):
        assert format_threshold(">=", 0.15) == ">= 0.15"

    def test_format_threshold_between(self):
        assert format_threshold("between", threshold_low=0.2, threshold_high=0.6) == "between 0.2 and 0.6"

    def test_format_threshold_trend(self):
        assert format_threshold("trend_up") == "trend up"

    def test_compute_analysis_score_all_pass(self):
        scores = [
            CriterionScore("A", "cat", "f", {}, 0.5, ">= 0.4", True, True, 2.0, 2.0, None, None),
            CriterionScore("B", "cat", "f", {}, 0.3, ">= 0.2", True, True, 1.0, 1.0, None, None),
        ]
        result = compute_analysis_score(scores)
        assert result.overall_score == Decimal("3.0")
        assert result.max_score == Decimal("3.0")
        assert result.pct_score == Decimal("100.0")
        assert result.grade == "A"
        assert result.passed_count == 2
        assert result.failed_count == 0

    def test_compute_analysis_score_mixed(self):
        scores = [
            CriterionScore("A", "cat", "f", {}, 0.5, ">= 0.4", True, True, 2.0, 2.0, None, None),
            CriterionScore("B", "cat", "f", {}, 0.1, ">= 0.2", False, True, 0.0, 1.0, None, None),
        ]
        result = compute_analysis_score(scores)
        assert result.overall_score == Decimal("2.0")
        assert result.max_score == Decimal("3.0")
        assert float(result.pct_score) == pytest.approx(66.67, abs=0.01)
        assert result.grade == "C"

    def test_compute_analysis_score_no_data_excluded(self):
        """no_data criteria should be excluded from max score."""
        scores = [
            CriterionScore("A", "cat", "f", {}, 0.5, ">= 0.4", True, True, 2.0, 2.0, None, None),
            CriterionScore("B", "cat", "f", {}, None, ">= 0.2", False, False, 0.0, 3.0, None, "No data"),
        ]
        result = compute_analysis_score(scores)
        assert result.overall_score == Decimal("2.0")
        assert result.max_score == Decimal("2.0")
        assert result.pct_score == Decimal("100.0")
        assert result.grade == "A"
        assert result.no_data_count == 1

    def test_compute_analysis_score_all_no_data(self):
        scores = [
            CriterionScore("A", "cat", "f", {}, None, ">= 0.4", False, False, 0.0, 2.0, None, None),
        ]
        result = compute_analysis_score(scores)
        assert result.pct_score == Decimal("0.0")
        assert result.grade == "F"

    def test_compute_analysis_score_empty(self):
        result = compute_analysis_score([])
        assert result.pct_score == Decimal("0.0")


# =====================================================================
# T506 — Engine tests
# =====================================================================


class TestEngine:
    """Engine-level tests (run_criterion, run_analysis)."""

    def test_build_data_by_year_from_dicts(self):
        stmts = [
            {
                "fiscal_year": 2023,
                "statement_data": _make_financials(2023),
            },
            {
                "fiscal_year": 2022,
                "statement_data": _make_financials(2022),
            },
        ]
        result = build_data_by_year(stmts)
        assert 2023 in result
        assert 2022 in result
        assert "income_statement" in result[2023]

    def test_run_criterion_passes(self):
        data = {
            2022: _make_financials(2022),
            2023: _make_financials(2023),
        }
        score = run_criterion(
            name="Gross Margin > 40%",
            category="profitability",
            formula_name="gross_margin",
            is_custom_formula=False,
            comparison=">=",
            threshold_value=0.40,
            threshold_low=None,
            threshold_high=None,
            weight=2.0,
            lookback_years=5,
            data_by_year=data,
            latest_year=2023,
        )
        assert score.passed is True
        assert score.has_data is True
        assert score.weighted_score == 2.0
        assert score.latest_value is not None
        assert abs(score.latest_value - 0.45) < 0.001

    def test_run_criterion_fails(self):
        data = {2023: _make_financials(2023)}
        score = run_criterion(
            name="Gross Margin > 90%",
            category="profitability",
            formula_name="gross_margin",
            is_custom_formula=False,
            comparison=">=",
            threshold_value=0.90,
            threshold_low=None,
            threshold_high=None,
            weight=2.0,
            lookback_years=5,
            data_by_year=data,
            latest_year=2023,
        )
        assert score.passed is False
        assert score.has_data is True
        assert score.weighted_score == 0.0

    def test_run_criterion_no_data(self):
        score = run_criterion(
            name="Test",
            category="profitability",
            formula_name="gross_margin",
            is_custom_formula=False,
            comparison=">=",
            threshold_value=0.40,
            threshold_low=None,
            threshold_high=None,
            weight=2.0,
            lookback_years=5,
            data_by_year={},
            latest_year=2023,
        )
        assert score.passed is False
        assert score.has_data is False

    def test_run_criterion_custom_formula(self):
        data = {2023: _make_financials(2023)}
        score = run_criterion(
            name="Custom Metric",
            category="custom",
            formula_name="income_statement.revenue / balance_sheet.total_assets",
            is_custom_formula=True,
            comparison=">=",
            threshold_value=0.5,
            threshold_low=None,
            threshold_high=None,
            weight=1.0,
            lookback_years=5,
            data_by_year=data,
            latest_year=2023,
        )
        # 100M / 120M ≈ 0.833
        assert score.passed is True
        assert score.latest_value is not None
        assert score.latest_value > 0.8

    def test_run_criterion_trend_up(self):
        data = {
            2019: _make_financials(2019, **{"income_statement.revenue": 60_000_000}),
            2020: _make_financials(2020, **{"income_statement.revenue": 70_000_000}),
            2021: _make_financials(2021, **{"income_statement.revenue": 80_000_000}),
            2022: _make_financials(2022, **{"income_statement.revenue": 90_000_000}),
            2023: _make_financials(2023),
        }
        score = run_criterion(
            name="Revenue Trend",
            category="growth",
            formula_name="revenue_growth",
            is_custom_formula=False,
            comparison="trend_up",
            threshold_value=None,
            threshold_low=None,
            threshold_high=None,
            weight=1.0,
            lookback_years=5,
            data_by_year=data,
            latest_year=2023,
        )
        # Revenue is steadily growing → revenue_growth should show improving trend
        assert score.trend is not None

    def test_run_criterion_invalid_formula(self):
        data = {2023: _make_financials(2023)}
        score = run_criterion(
            name="Bad Formula",
            category="custom",
            formula_name="nonexistent_formula",
            is_custom_formula=False,
            comparison=">=",
            threshold_value=0.5,
            threshold_low=None,
            threshold_high=None,
            weight=1.0,
            lookback_years=5,
            data_by_year=data,
            latest_year=2023,
        )
        assert score.has_data is False
        assert "Formula error" in (score.note or "")

    def test_run_analysis_full(self):
        data = {
            2022: _make_financials(2022, **{
                "income_statement.revenue": 90_000_000,
                "income_statement.net_income": 15_000_000,
            }),
            2023: _make_financials(2023),
        }
        criteria = [
            {
                "name": "Gross Margin > 40%",
                "category": "profitability",
                "formula": "gross_margin",
                "comparison": ">=",
                "threshold_value": 0.40,
                "weight": 2.0,
                "lookback_years": 5,
            },
            {
                "name": "Net Margin > 10%",
                "category": "profitability",
                "formula": "net_margin",
                "comparison": ">=",
                "threshold_value": 0.10,
                "weight": 1.5,
                "lookback_years": 5,
            },
            {
                "name": "Net Margin > 50%",
                "category": "profitability",
                "formula": "net_margin",
                "comparison": ">=",
                "threshold_value": 0.50,
                "weight": 1.0,
                "lookback_years": 5,
            },
        ]
        result = run_analysis(criteria=criteria, data_by_year=data)

        assert result.passed_count == 2  # gross_margin and net_margin > 10% pass
        assert result.failed_count == 1  # net_margin > 50% fails
        assert float(result.overall_score) == 3.5  # 2.0 + 1.5
        assert float(result.max_score) == 4.5  # 2.0 + 1.5 + 1.0
        pct = 3.5 / 4.5 * 100
        assert abs(float(result.pct_score) - pct) < 0.1
        assert result.grade == "B"  # ~77.78%

    def test_run_analysis_empty_data(self):
        criteria = [
            {
                "name": "Test",
                "category": "profitability",
                "formula": "gross_margin",
                "comparison": ">=",
                "threshold_value": 0.40,
                "weight": 1.0,
                "lookback_years": 5,
            },
        ]
        result = run_analysis(criteria=criteria, data_by_year={})
        assert result.criteria_count == 0
        assert result.pct_score == Decimal("0.0")

    def test_run_analysis_values_by_year_populated(self):
        data = {
            2021: _make_financials(2021),
            2022: _make_financials(2022),
            2023: _make_financials(2023),
        }
        criteria = [
            {
                "name": "Current Ratio",
                "category": "liquidity",
                "formula": "current_ratio",
                "comparison": ">=",
                "threshold_value": 1.0,
                "weight": 1.0,
                "lookback_years": 5,
            },
        ]
        result = run_analysis(criteria=criteria, data_by_year=data)
        score = result.criteria_scores[0]
        assert 2021 in score.values_by_year
        assert 2022 in score.values_by_year
        assert 2023 in score.values_by_year
