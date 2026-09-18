"""One lock order, kept by every path that concludes a ticket reservation.

Two paths that take the same rows in opposite orders can deadlock: each ends up holding what the
other is waiting for, and the database resolves that by killing one of them — which, on this code,
means a payment that is neither confirmed nor released. So the order is a convention rather than a
comment: Payment, then Order, then Ticket, established by the successful-payment path and followed
by every path that finalizes, releases or expires a reservation.

SQLite ignores ``FOR UPDATE``, so a test that runs those paths cannot prove the order they take —
it would pass just as happily on a codebase that had them inverted. This one reads the source
instead, and fails on the arrangement rather than on the outcome.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

LOCK_ORDER = ("Payment", "Order", "Ticket")

# Every path that locks a payment, an order, or both, and therefore has an order to keep. A new one
# belongs here — that is what the second test below is for.
LOCKING_PATHS = {
    "src/services/payment.py": ("apply_successful_payment", "cancel_pending_checkout"),
    "src/services/ticket.py": ("expire_pending_orders", "release_pending_order"),
}
LOCKING_PATH_SET = {
    (path, name) for path, names in LOCKING_PATHS.items() for name in names
}

# The rows a path must never take out of order. These two are what the deadlock is made of: a
# finalizing path holds the payment and wants the order, while a sweeping path held the order and
# wanted the payment.
CONTESTED = {"Payment", "Order"}


def _select_target(node: ast.AST) -> str | None:
    """The entity named by the outermost ``select(...)`` in a ``for update`` call chain."""
    current = node
    while isinstance(current, ast.Call):
        function = current.func
        if isinstance(function, ast.Name):
            if function.id == "select" and current.args:
                return ast.unparse(current.args[0]).split(".")[0]
            return None
        if isinstance(function, ast.Attribute):
            current = function.value
            continue
        return None
    return None


def locked_rows(function: ast.FunctionDef) -> list[str]:
    """Entities whose rows a function locks, in the order the source takes them."""
    found = []
    for node in ast.walk(function):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "with_for_update"):
            continue
        target = _select_target(node.func.value)
        if target is not None:
            # Source order, not walk order: which of two locks comes first is the thing being read.
            found.append((node.lineno, target))
    taken: list[str] = []
    for _, target in sorted(found):
        if target not in taken:
            taken.append(target)
    return taken


def functions_locking_rows(path: Path) -> dict[str, list[str]]:
    """Every function in a file that locks a row, and which rows each one locks."""
    found: dict[str, list[str]] = {}
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.FunctionDef):
            continue
        entities = locked_rows(node)
        if entities:
            found[node.name] = entities
    return found


@pytest.mark.parametrize("path,names", sorted(LOCKING_PATHS.items()))
def test_reservation_paths_take_their_rows_in_the_documented_order(path, names):
    source = (ROOT / path).read_text(encoding="utf-8")
    checked = set()
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.FunctionDef) and node.name in names):
            continue
        checked.add(node.name)
        taken = locked_rows(node)
        # A path may lock a subset of the convention — nothing here locks payment rows without also
        # locking its order — but never a subset out of order.
        assert taken == [entity for entity in LOCK_ORDER if entity in taken], (
            f"{path}:{node.name} locks {' -> '.join(taken)}, which is not the documented "
            f"{' -> '.join(LOCK_ORDER)} order"
        )
    # A renamed path would otherwise drop out of this test without saying so.
    assert checked == set(names), f"{path} no longer defines {sorted(set(names) - checked)}"


def test_only_the_documented_paths_lock_payment_or_order_rows():
    """A path that locks these rows joins the convention rather than quietly stepping around it."""
    found = {
        (str(file.relative_to(ROOT)).replace("\\", "/"), name)
        for file in (ROOT / "src").rglob("*.py")
        for name, entities in functions_locking_rows(file).items()
        if CONTESTED & set(entities)
    }
    assert found == LOCKING_PATH_SET, (
        "these functions lock a payment or an order row; add them to LOCKING_PATHS so the order "
        "they take their locks in is checked too"
    )
