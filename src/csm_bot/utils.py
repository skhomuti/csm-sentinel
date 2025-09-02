from typing import List


def chunk_text(s: str, limit: int = 4000) -> List[str]:
    """Split text into chunks not exceeding the given character limit.

    Splits on newline boundaries when possible; if a single line exceeds the
    limit, it is split into fixed-size chunks. The default limit stays below
    Telegram's ~4096-character message cap.
    """
    if len(s) <= limit:
        return [s]

    parts: List[str] = []
    current: str = ""

    for line in s.split("\n"):
        # If a single line is longer than the limit, flush current and slice it
        while len(line) > limit:
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:limit])
            line = line[limit:]

        # Now the line fits within the limit; try to append to current
        if not current:
            current = line
        elif len(current) + 1 + len(line) <= limit:
            current += "\n" + line
        else:
            parts.append(current)
            current = line

    if current:
        parts.append(current)

    return parts
