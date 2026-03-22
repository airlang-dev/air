"""AIR type → Bedrock type mapping."""

AIR_TO_BEDROCK_TYPE: dict[str, str] = {
    "Message": "String",
    "Verdict": "String",
    "Outcome": "String",
    "String": "String",
    "str": "String",
    "int": "Number",
    "float": "Number",
    "Number": "Number",
    "bool": "Boolean",
    "Boolean": "Boolean",
}


def air_type_to_bedrock(air_type: str | None) -> str:
    """Map an AIR output type string to a Bedrock type literal.

    Rules (applied in order):
    1. If air_type ends with '[]' → 'Array'
    2. If air_type is in AIR_TO_BEDROCK_TYPE → mapped value
    3. If air_type is a capitalized identifier (Claim, Artifact, Consensus, etc.) → 'Object'
    4. Default → 'String'
    """
    if air_type is None:
        return "String"
    if air_type.endswith("[]"):
        return "Array"
    if air_type in AIR_TO_BEDROCK_TYPE:
        return AIR_TO_BEDROCK_TYPE[air_type]
    # Capitalized identifiers are structured record types → Object
    if air_type and air_type[0].isupper():
        return "Object"
    return "String"
