import pytest

from csm_bot.module_types import ModuleType, decode_module_type


def _bytes32(value: str) -> bytes:
    raw = value.encode("utf-8")
    return raw + b"\x00" * (32 - len(raw))


def test_decode_module_type_bytes():
    raw = _bytes32(ModuleType.COMMUNITY.value)
    assert decode_module_type(raw) == ModuleType.COMMUNITY


def test_decode_module_type_hex_str():
    raw = _bytes32(ModuleType.CURATED.value)
    assert decode_module_type("0x" + raw.hex()) == ModuleType.CURATED


def test_decode_module_type_unknown():
    with pytest.raises(RuntimeError) as exc:
        decode_module_type(_bytes32("unknown-module"))
    message = str(exc.value)
    assert "unknown-module" in message
    assert "raw:" in message
