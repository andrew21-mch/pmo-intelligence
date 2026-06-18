import re


def markdown_to_plain_text(text: str, *, max_len: int | None = None) -> str:
    """Strip markdown formatting for readable citation excerpts and previews."""
    parts: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("|") or stripped == "---":
            continue
        if stripped.startswith("### "):
            stripped = stripped[4:]
        elif stripped.startswith("## "):
            stripped = stripped[3:]
        elif stripped.startswith("# "):
            stripped = stripped[2:]
        elif stripped.startswith("- "):
            stripped = stripped[2:]
        stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        stripped = re.sub(r"\*(.+?)\*", r"\1", stripped)
        parts.append(stripped)

    plain = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if max_len is not None and len(plain) > max_len:
        trimmed = plain[: max_len - 1].rsplit(" ", 1)[0]
        return f"{trimmed}…"
    return plain
