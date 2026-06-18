import re

MAX_CHUNK = 800
OVERLAP = 100


def chunk_text(text: str) -> list[str]:
    """Split document into chunks by section headers or paragraph groups."""
    text = text.strip()
    if not text:
        return []

    sections = re.split(r"\n(?=#{1,3}\s|\d+\.\s+[A-Z])", text)
    chunks: list[str] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= MAX_CHUNK:
            chunks.append(section)
            continue
        paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= MAX_CHUNK:
                current = f"{current}\n\n{para}".strip() if current else para
            else:
                if current:
                    chunks.append(current)
                if len(para) <= MAX_CHUNK:
                    current = para
                else:
                    for i in range(0, len(para), MAX_CHUNK - OVERLAP):
                        chunks.append(para[i : i + MAX_CHUNK])
                    current = ""
        if current:
            chunks.append(current)

    return chunks or [text[:MAX_CHUNK]]
