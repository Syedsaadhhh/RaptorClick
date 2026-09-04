from app.models import ExecutionReceipt, HedgeRun

RUNS: dict[str, HedgeRun] = {}
RECEIPTS_BY_IDEMPOTENCY: dict[str, ExecutionReceipt] = {}
REACTIONS_BY_IDEMPOTENCY: set[str] = set()
