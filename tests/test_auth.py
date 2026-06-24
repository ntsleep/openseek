from seeklite.auth import compute_auth_byte


def test_empty_payload():
    assert compute_auth_byte(b"") == 0


def test_single_byte():
    assert compute_auth_byte(b"\xAB") == 0xAB


def test_two_bytes():
    assert compute_auth_byte(b"\x01\x02") == 0x03


def test_known_manufacturer_payload():
    payload = b"\xde\xad\xbe\xef\xca\xfe"
    assert compute_auth_byte(payload) == 0x16


def test_xor_is_commutative():
    a = b"\x12\x34\x56\x78"
    b = b"\x78\x56\x34\x12"
    assert compute_auth_byte(a) == compute_auth_byte(b)


def test_all_zeros():
    assert compute_auth_byte(b"\x00\x00\x00") == 0


def test_long_payload():
    payload = bytes(range(256))
    expected = 0
    for b in payload:
        expected ^= b
    assert compute_auth_byte(payload) == expected
