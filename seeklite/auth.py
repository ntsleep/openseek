def compute_auth_byte(payload: bytes) -> int:
    result = 0
    for b in payload:
        result ^= b
    return result
