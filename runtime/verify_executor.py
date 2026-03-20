"""Verify execution for the AIR Agent VM.

Resolves rule assets and uses LLM to evaluate input against rules.
Returns (verdict, evidence) tuples.
"""

import re

import litellm


class VerifyExecutor:
    """Executes verify operations via LLM-based rule evaluation."""

    def __init__(self, asset_resolver, config):
        self._asset_resolver = asset_resolver
        self._config = config

    def execute(self, input_val, rule_name):
        """Verify input against a rule. Returns (verdict, evidence) tuple."""
        asset = self._asset_resolver.resolve_rule(rule_name)
        model = asset.model or self._config.default_model
        user_content = (
            "Evaluate the following against this rule. "
            "Respond with PASS, FAIL, or UNCERTAIN, then explain.\n\n"
            f"Rule: {asset.template}\n\n"
            f"Input: {input_val}"
        )

        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": user_content}],
        )
        evidence = response.choices[0].message.content
        verdict = self._parse_verdict(evidence)
        return (verdict, evidence)

    def _parse_verdict(self, text):
        """Extract PASS/FAIL/UNCERTAIN from LLM response text."""
        match = re.search(r"\b(PASS|FAIL|UNCERTAIN)\b", text)
        if match:
            return match.group(1)
        return "UNCERTAIN"
