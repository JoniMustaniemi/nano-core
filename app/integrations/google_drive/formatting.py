from __future__ import annotations


def format_file_metadata(metadata: dict[str, str | int | None]) -> str:
    name = metadata.get("name") or "(untitled)"
    mime = metadata.get("mimeType") or "unknown"
    size = metadata.get("size")
    file_id = metadata.get("id") or ""
    lines = [f"Name: {name}", f"Type: {mime}", f"ID: {file_id}"]
    if size is not None:
        lines.append(f"Size: {size} bytes")
    return "\n".join(lines)


def format_file_content(
    name: str,
    content: str,
    *,
    truncated: bool,
) -> str:
    header = f"File: {name}"
    body = content
    if truncated:
        body = f"{content}\n\n(truncated)"
    return f"{header}\n\n{body}"
