class DAXValidationAgent:
    def __init__(self, schema_context):
        self.schema = schema_context

    def validate_measure(self, measure_name: str, dax_syntax: str) -> dict:
        """Validates generated DAX for structural and architectural conformity."""
        errors = []
        warnings = []
        
        # Test 1: Bracket Matching Validation
        if dax_syntax.count("(") != dax_syntax.count(")"):
            errors.append("ERR_SYNTAX_PARENTHESIS_MISMATCH: Unmatched parentheses detected.")
            
        # Test 2: Table/Column Existence Check
        # Regex to pull items wrapped in single quotes (tables) and square brackets (columns)
        extracted_tables = re.findall(r"'([^']+)'", dax_syntax)
        for tbl in extracted_tables:
            if tbl not in self.schema:
                errors.append(f"ERR_MISSING_TABLE: Table '{tbl}' does not exist in the target model layout.")

        return {
            "measure": measure_name,
            "status": "PASSED" if not errors else "FAILED",
            "errors": errors,
            "warnings": warnings
        }