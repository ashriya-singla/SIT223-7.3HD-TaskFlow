"""Task domain validation, independent of HTTP and database access."""

STATUSES = {"todo", "doing", "done"}
PRIORITIES = {"low", "medium", "high"}


def validate_task(data, partial=False):
    """Reject unknown fields and enforce domain constraints before persistence."""
    if not isinstance(data, dict) or set(data) - {"title", "status", "priority"}:
        raise ValueError("Expected title, status and priority fields")
    result = {}
    if "title" in data or not partial:
        title = data.get("title", "")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError("Title must contain 1 to 120 characters")
        result["title"] = title.strip()
    for field, allowed, default in [
        ("status", STATUSES, "todo"),
        ("priority", PRIORITIES, "medium"),
    ]:
        if field in data or not partial:
            value = data.get(field, default)
            if not isinstance(value, str) or value not in allowed:
                raise ValueError(f"Invalid {field}")
            result[field] = value
    if not result:
        raise ValueError("At least one field is required")
    return result
