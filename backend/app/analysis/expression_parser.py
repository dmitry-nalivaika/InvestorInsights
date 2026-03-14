# filepath: backend/app/analysis/expression_parser.py
"""Custom formula expression parser and evaluator.

Implements a lexer → recursive-descent parser → AST evaluator that
supports:
  - Field references: ``income_statement.revenue``
  - Arithmetic:       ``+ - * / ^``
  - Parentheses:      ``( )``
  - Functions:         ``abs(x)``, ``min(a, b)``, ``max(a, b)``, ``avg(a, b, ...)``
  - Previous period:   ``prev(field)`` or ``prev(field, lookback)``
  - Numeric literals:  ``0.21``, ``1``, ``100``
  - Unary minus:       ``-x``

Grammar (EBNF)::

    expr       → term (( '+' | '-' ) term)*
    term       → power (( '*' | '/' ) power)*
    power      → unary ( '^' power )?
    unary      → '-' unary | call
    call       → IDENT '(' args ')' | atom
    args       → expr ( ',' expr )*
    atom       → NUMBER | field_ref | '(' expr ')'
    field_ref  → IDENT '.' IDENT

Tasks: T501 (parser), T502 (prev() resolution), T503 (validation)
"""

from __future__ import annotations

import enum
import math
import re
from dataclasses import dataclass
from typing import Any

from app.observability.logging import get_logger

logger = get_logger(__name__)

# ── Tokens ───────────────────────────────────────────────────────


class TokenType(enum.Enum):
    NUMBER = "NUMBER"
    IDENT = "IDENT"
    DOT = "DOT"
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    CARET = "CARET"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COMMA = "COMMA"
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: str
    pos: int


# ── Lexer ────────────────────────────────────────────────────────

_TOKEN_SPEC = [
    (TokenType.NUMBER, r"\d+(?:\.\d+)?"),
    (TokenType.IDENT, r"[a-zA-Z_][a-zA-Z0-9_]*"),
    (TokenType.DOT, r"\."),
    (TokenType.PLUS, r"\+"),
    (TokenType.MINUS, r"-"),
    (TokenType.STAR, r"\*"),
    (TokenType.SLASH, r"/"),
    (TokenType.CARET, r"\^"),
    (TokenType.LPAREN, r"\("),
    (TokenType.RPAREN, r"\)"),
    (TokenType.COMMA, r","),
]

_TOKEN_REGEX = re.compile(
    "|".join(f"(?P<{tt.name}>{pattern})" for tt, pattern in _TOKEN_SPEC),
)

_WHITESPACE = re.compile(r"\s+")


class LexError(Exception):
    """Raised on unexpected characters during lexing."""


class ParseError(Exception):
    """Raised on syntax errors during parsing."""


class EvalError(Exception):
    """Raised on runtime errors during evaluation (e.g. division by zero)."""


def tokenize(source: str) -> list[Token]:
    """Tokenize a formula expression string."""
    tokens: list[Token] = []
    pos = 0
    while pos < len(source):
        ws = _WHITESPACE.match(source, pos)
        if ws:
            pos = ws.end()
            continue
        m = _TOKEN_REGEX.match(source, pos)
        if not m:
            raise LexError(f"Unexpected character {source[pos]!r} at position {pos}")
        for tt, _ in _TOKEN_SPEC:
            val = m.group(tt.name)
            if val is not None:
                tokens.append(Token(tt, val, pos))
                break
        pos = m.end()
    tokens.append(Token(TokenType.EOF, "", pos))
    return tokens


# ── AST Nodes ────────────────────────────────────────────────────


@dataclass
class NumberNode:
    value: float


@dataclass
class FieldRefNode:
    """Reference to a financial data field: e.g. income_statement.revenue."""
    statement: str
    field: str

    @property
    def full_name(self) -> str:
        return f"{self.statement}.{self.field}"


@dataclass
class PrevNode:
    """prev(field) or prev(field, lookback) — previous period reference."""
    field: FieldRefNode
    lookback: int = 1


@dataclass
class UnaryOpNode:
    op: str
    operand: Any


@dataclass
class BinOpNode:
    op: str
    left: Any
    right: Any


@dataclass
class FuncCallNode:
    name: str
    args: list[Any]


# ── Parser ───────────────────────────────────────────────────────

_VALID_STATEMENTS = {"income_statement", "balance_sheet", "cash_flow"}
_BUILTIN_FUNCTIONS = {"abs", "min", "max", "avg", "prev"}


class Parser:
    """Recursive-descent parser for formula expressions."""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    @property
    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, tt: TokenType) -> Token:
        tok = self._current
        if tok.type != tt:
            raise ParseError(
                f"Expected {tt.value} but got {tok.type.value} ({tok.value!r}) at pos {tok.pos}",
            )
        return self._advance()

    # ── Grammar rules ────────────────────────────────────────────

    def parse(self) -> Any:
        """Parse the full expression and return an AST node."""
        node = self._expr()
        if self._current.type != TokenType.EOF:
            tok = self._current
            raise ParseError(f"Unexpected token {tok.value!r} at pos {tok.pos}")
        return node

    def _expr(self) -> Any:
        """expr → term (( '+' | '-' ) term)*"""
        left = self._term()
        while self._current.type in (TokenType.PLUS, TokenType.MINUS):
            op = self._advance().value
            right = self._term()
            left = BinOpNode(op, left, right)
        return left

    def _term(self) -> Any:
        """term → power (( '*' | '/' ) power)*"""
        left = self._power()
        while self._current.type in (TokenType.STAR, TokenType.SLASH):
            op = self._advance().value
            right = self._power()
            left = BinOpNode(op, left, right)
        return left

    def _power(self) -> Any:
        """power → unary ( '^' power )?  (right-associative)"""
        base = self._unary()
        if self._current.type == TokenType.CARET:
            self._advance()
            exp = self._power()
            return BinOpNode("^", base, exp)
        return base

    def _unary(self) -> Any:
        """unary → '-' unary | call"""
        if self._current.type == TokenType.MINUS:
            self._advance()
            operand = self._unary()
            return UnaryOpNode("-", operand)
        return self._call()

    def _call(self) -> Any:
        """call → IDENT '(' args ')' | atom"""
        if (
            self._current.type == TokenType.IDENT
            and self._pos + 1 < len(self._tokens)
            and self._tokens[self._pos + 1].type == TokenType.LPAREN
        ):
            name_tok = self._advance()
            name = name_tok.value

            # Check for field_ref followed by something that's not '('
            # This is already handled by the lookahead above

            if name not in _BUILTIN_FUNCTIONS and name not in _VALID_STATEMENTS:
                raise ParseError(f"Unknown function {name!r} at pos {name_tok.pos}")

            # It might be a statement like income_statement.revenue(...)
            # which would be invalid — but we only enter here if next is LPAREN
            # and name is a function name.
            if name in _VALID_STATEMENTS:
                # This is actually a field ref with parens context — fall back
                self._pos -= 1
                return self._atom()

            self._advance()  # consume '('
            args = self._args()
            self._expect(TokenType.RPAREN)

            if name == "prev":
                return self._build_prev_node(args, name_tok.pos)

            return FuncCallNode(name, args)

        return self._atom()

    def _args(self) -> list[Any]:
        """args → expr ( ',' expr )*"""
        if self._current.type == TokenType.RPAREN:
            return []
        result = [self._expr()]
        while self._current.type == TokenType.COMMA:
            self._advance()
            result.append(self._expr())
        return result

    def _atom(self) -> Any:
        """atom → NUMBER | field_ref | '(' expr ')'"""
        tok = self._current

        if tok.type == TokenType.NUMBER:
            self._advance()
            return NumberNode(float(tok.value))

        if tok.type == TokenType.IDENT:
            return self._field_ref()

        if tok.type == TokenType.LPAREN:
            self._advance()
            node = self._expr()
            self._expect(TokenType.RPAREN)
            return node

        raise ParseError(
            f"Unexpected token {tok.type.value} ({tok.value!r}) at pos {tok.pos}",
        )

    def _field_ref(self) -> FieldRefNode:
        """field_ref → IDENT '.' IDENT"""
        stmt_tok = self._expect(TokenType.IDENT)
        stmt = stmt_tok.value
        if stmt not in _VALID_STATEMENTS:
            raise ParseError(
                f"Invalid statement {stmt!r} at pos {stmt_tok.pos}. "
                f"Expected one of: {', '.join(sorted(_VALID_STATEMENTS))}",
            )
        self._expect(TokenType.DOT)
        field_tok = self._expect(TokenType.IDENT)
        return FieldRefNode(stmt, field_tok.value)

    def _build_prev_node(self, args: list[Any], pos: int) -> PrevNode:
        """Build a PrevNode from prev() function arguments."""
        if not args or len(args) > 2:
            raise ParseError(
                f"prev() requires 1-2 arguments at pos {pos}",
            )
        field_arg = args[0]
        if not isinstance(field_arg, FieldRefNode):
            raise ParseError(
                f"prev() first argument must be a field reference at pos {pos}",
            )
        lookback = 1
        if len(args) == 2:
            lb_arg = args[1]
            if not isinstance(lb_arg, NumberNode) or lb_arg.value != int(lb_arg.value):
                raise ParseError(
                    f"prev() second argument must be an integer at pos {pos}",
                )
            lookback = int(lb_arg.value)
            if lookback < 1:
                raise ParseError(
                    f"prev() lookback must be >= 1 at pos {pos}",
                )
        return PrevNode(field_arg, lookback)


# ── Public parse function ────────────────────────────────────────


def parse_expression(source: str) -> Any:
    """Parse a formula expression string into an AST.

    Args:
        source: The formula expression.

    Returns:
        An AST node tree.

    Raises:
        LexError: On tokenization failures.
        ParseError: On syntax errors.
    """
    tokens = tokenize(source)
    parser = Parser(tokens)
    return parser.parse()


# ── Validation (T503) ────────────────────────────────────────────


def validate_expression(source: str) -> list[str]:
    """Validate a formula expression and return a list of error messages.

    Returns an empty list if the expression is valid.
    """
    errors: list[str] = []

    # Check balanced parentheses
    depth = 0
    for ch in source:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                errors.append("Unbalanced parentheses: extra closing ')'")
                break
    if depth > 0:
        errors.append(f"Unbalanced parentheses: {depth} unclosed '('")

    # Try full parse
    try:
        ast = parse_expression(source)
    except (LexError, ParseError) as exc:
        errors.append(str(exc))
        return errors

    # Collect field references and validate them
    fields = collect_field_refs(ast)
    for field_name in fields:
        parts = field_name.split(".")
        if len(parts) != 2:
            errors.append(f"Invalid field reference: {field_name}")
        elif parts[0] not in _VALID_STATEMENTS:
            errors.append(
                f"Unknown statement type {parts[0]!r} in {field_name}",
            )

    return errors


def collect_field_refs(node: Any) -> list[str]:
    """Recursively collect all field references from an AST."""
    refs: list[str] = []
    _collect(node, refs)
    return refs


def _collect(node: Any, refs: list[str]) -> None:
    """Recursive helper for collect_field_refs."""
    if isinstance(node, FieldRefNode):
        refs.append(node.full_name)
    elif isinstance(node, PrevNode):
        refs.append(node.field.full_name)
    elif isinstance(node, UnaryOpNode):
        _collect(node.operand, refs)
    elif isinstance(node, BinOpNode):
        _collect(node.left, refs)
        _collect(node.right, refs)
    elif isinstance(node, FuncCallNode):
        for arg in node.args:
            _collect(arg, refs)
    # NumberNode — no refs


# ── Evaluator (T502 — prev() resolution) ─────────────────────────


class FormulaContext:
    """Evaluation context holding financial data for a company across years.

    Attributes:
        data_by_year: Mapping of fiscal_year → statement_data dict.
            Each statement_data has keys like ``income_statement``,
            ``balance_sheet``, ``cash_flow`` mapping to field dicts.
        current_year: The year being evaluated.
    """

    def __init__(
        self,
        data_by_year: dict[int, dict[str, dict[str, Any]]],
        current_year: int,
    ) -> None:
        self.data_by_year = data_by_year
        self.current_year = current_year

    def get_field(self, statement: str, field: str) -> float | None:
        """Resolve a field value for the current year."""
        year_data = self.data_by_year.get(self.current_year, {})
        stmt_data = year_data.get(statement, {})
        val = stmt_data.get(field)
        return _to_float(val)

    def get_prev_field(
        self,
        statement: str,
        field: str,
        lookback: int = 1,
    ) -> float | None:
        """Resolve a field value from a previous period.

        Searches backwards from current_year - lookback.
        """
        target_year = self.current_year - lookback
        year_data = self.data_by_year.get(target_year, {})
        stmt_data = year_data.get(statement, {})
        val = stmt_data.get(field)
        return _to_float(val)


def _to_float(val: Any) -> float | None:
    """Convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def evaluate(node: Any, ctx: FormulaContext) -> float | None:
    """Evaluate an AST node against a FormulaContext.

    Returns None if any required field data is missing (null propagation).

    Raises:
        EvalError: On runtime errors (e.g. division by zero).
    """
    if isinstance(node, NumberNode):
        return node.value

    if isinstance(node, FieldRefNode):
        return ctx.get_field(node.statement, node.field)

    if isinstance(node, PrevNode):
        return ctx.get_prev_field(node.field.statement, node.field.field, node.lookback)

    if isinstance(node, UnaryOpNode):
        val = evaluate(node.operand, ctx)
        if val is None:
            return None
        if node.op == "-":
            return -val
        return val  # pragma: no cover

    if isinstance(node, BinOpNode):
        left = evaluate(node.left, ctx)
        right = evaluate(node.right, ctx)
        if left is None or right is None:
            return None
        return _eval_binop(node.op, left, right)

    if isinstance(node, FuncCallNode):
        return _eval_func(node.name, node.args, ctx)

    raise EvalError(f"Unknown AST node type: {type(node).__name__}")  # pragma: no cover


def _eval_binop(op: str, left: float, right: float) -> float | None:
    """Evaluate a binary operation."""
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if right == 0:
            return None  # Division by zero → null (not an error)
        return left / right
    if op == "^":
        try:
            return left ** right
        except (OverflowError, ValueError):
            return None
    raise EvalError(f"Unknown operator: {op}")  # pragma: no cover


def _eval_func(name: str, args: list[Any], ctx: FormulaContext) -> float | None:
    """Evaluate a built-in function call."""
    evaluated = [evaluate(arg, ctx) for arg in args]

    if name == "abs":
        if len(evaluated) != 1:
            raise EvalError("abs() requires exactly 1 argument")
        return abs(evaluated[0]) if evaluated[0] is not None else None

    if name == "min":
        non_null = [v for v in evaluated if v is not None]
        return min(non_null) if non_null else None

    if name == "max":
        non_null = [v for v in evaluated if v is not None]
        return max(non_null) if non_null else None

    if name == "avg":
        non_null = [v for v in evaluated if v is not None]
        if not non_null:
            return None
        return sum(non_null) / len(non_null)

    raise EvalError(f"Unknown function: {name}")  # pragma: no cover


# ── Convenience ──────────────────────────────────────────────────


def compute_formula(
    expression: str,
    data_by_year: dict[int, dict[str, dict[str, Any]]],
    year: int,
) -> float | None:
    """Parse and evaluate a formula expression for a given year.

    Returns None when data is missing or computation is undefined.
    """
    ast = parse_expression(expression)
    ctx = FormulaContext(data_by_year, year)
    return evaluate(ast, ctx)
