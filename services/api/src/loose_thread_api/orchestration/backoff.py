import hashlib
from datetime import timedelta


def retry_delay(attempt: int, idempotency_key: str) -> timedelta:
    if attempt <= 0:
        raise ValueError("attempt must be positive")

    if attempt == 1:
        lower, upper = 5, 10
    elif attempt == 2:
        lower, upper = 10, 15
    elif attempt == 3:
        lower, upper = 60, 75
    else:
        lower, upper = 300, 360

    digest = hashlib.sha256(f"{idempotency_key}:{attempt}".encode()).digest()
    offset = int.from_bytes(digest[:2], "big") % (upper - lower + 1)
    return timedelta(seconds=lower + offset)
