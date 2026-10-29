"""AST node classes produced by the parser and walked by the interpreter."""

from dataclasses import dataclass, field
from typing import List, Optional


class Node:
    line: int = 0


# -- expressions -------------------------------------------------------------

@dataclass
class Num(Node):
    value: object
    line: int = 0


@dataclass
class Str(Node):
    value: str
    line: int = 0


@dataclass
class Id(Node):
    name: str
    line: int = 0


@dataclass
class Colon(Node):
    """A bare ':' used as an index (all elements)."""
    line: int = 0


@dataclass
class End(Node):
    """`end` used inside an index (last element)."""
    line: int = 0


@dataclass
class Binary(Node):
    op: str
    left: Node
    right: Node
    line: int = 0


@dataclass
class Unary(Node):
    op: str
    operand: Node
    line: int = 0


@dataclass
class Postfix(Node):
    op: str          # "'" or ".'"
    operand: Node
    line: int = 0


@dataclass
class Index(Node):
    target: Node
    args: List[Node]
    brace: bool = False   # True for c{...}
    line: int = 0


@dataclass
class Field(Node):
    target: Node
    name: str
    line: int = 0


@dataclass
class Matrix(Node):
    rows: List[List[Node]]
    cell: bool = False    # True for { ... }
    line: int = 0


@dataclass
class Range(Node):
    start: Node
    step: Optional[Node]
    stop: Node
    line: int = 0


@dataclass
class AnonFunc(Node):
    params: List[str]
    body: Node
    line: int = 0


@dataclass
class FuncHandle(Node):
    name: str
    line: int = 0


# -- statements --------------------------------------------------------------

@dataclass
class ExprStmt(Node):
    expr: Node
    show: bool
    line: int = 0


@dataclass
class Assign(Node):
    targets: List[Node]
    expr: Node
    show: bool
    line: int = 0


@dataclass
class If(Node):
    clauses: list          # list of (cond, body)
    orelse: Optional[list]
    line: int = 0


@dataclass
class For(Node):
    var: str
    expr: Node
    body: list
    line: int = 0


@dataclass
class While(Node):
    cond: Node
    body: list
    line: int = 0


@dataclass
class Switch(Node):
    expr: Node
    cases: list            # list of (value_expr, body)
    otherwise: Optional[list]
    line: int = 0


@dataclass
class Break(Node):
    line: int = 0


@dataclass
class Continue(Node):
    line: int = 0


@dataclass
class Return(Node):
    line: int = 0


@dataclass
class Command(Node):
    name: str
    args: List[str]
    show: bool = True
    line: int = 0


@dataclass
class FunctionDef(Node):
    name: str
    params: List[str]
    outputs: List[str]
    body: list
    line: int = 0


@dataclass
class Program(Node):
    body: list
    functions: dict = field(default_factory=dict)
    line: int = 0
