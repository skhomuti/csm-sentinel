from enum import StrEnum

from hexbytes import HexBytes


class ModuleType(StrEnum):
    COMMUNITY = "community-onchain-v1"
    CURATED = "curated-onchain-v2"


def _decode_raw_module_type(raw: bytes | HexBytes | str) -> str:
    if isinstance(raw, (bytes, bytearray, HexBytes)):
        return bytes(raw).rstrip(b"\x00").decode("utf-8", errors="replace")
    if isinstance(raw, str):
        if raw.startswith("0x"):
            try:
                raw_bytes = bytes.fromhex(raw[2:])
            except ValueError:
                return raw
            return raw_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
        return raw
    raise TypeError(f"Unsupported module type value: {type(raw)!r}")


def decode_module_type(raw: bytes | HexBytes | str) -> ModuleType:
    decoded = _decode_raw_module_type(raw)
    try:
        return ModuleType(decoded)
    except ValueError as exc:
        raw_hex = raw.hex() if isinstance(raw, (bytes, bytearray, HexBytes)) else raw
        raise RuntimeError(
            f"Unknown module type '{decoded}' (raw: {raw_hex})"
        ) from exc
