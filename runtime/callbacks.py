"""Pluggable callbacks for the AIR runtime.

Swap these with custom implementations (TUI, web, API) by assigning
to RuntimeConfig.human_callback.
"""


def stdin_callback(provider, input_val):
    """Interactive terminal callback for human decisions."""
    print(f"\n[HUMAN] Decision requested by provider: {provider}")
    print(f"[HUMAN] Input: {input_val}")
    return input("[HUMAN] Enter outcome (PROCEED/RETRY/ESCALATE/HALT): ").strip()
