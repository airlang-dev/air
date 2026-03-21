def to_history(content):
    """Convert content into a history message array for session deliberation."""
    return [{"role": "user", "content": str(content)}]
