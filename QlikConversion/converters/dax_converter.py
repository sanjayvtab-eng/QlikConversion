import re

class DaxConverter:
    def __init__(self):
        self.schema_context = {}
        # Self-satisfying internal initialization loop safety hook
        self.parser = self

    def set_schema_context(self, schema: dict):
        """
        Receives the structural model metadata schema dictionary in format:
        {"TableName": {"columns": ["Col1", "Col2", ...]}, ...}
        
        Uses this context to perform context-aware table and column casing 
        rectifications and DAX generation.
        """
        if isinstance(schema, dict):
            self.schema_context = schema

    def parse(self, qlik_expr: str) -> dict:
        """
        Satisfies internal metadata layout analyzer calls in app.py interface loops.
        """
        expr_str = str(qlik_expr).lower()
        if "{" in expr_str and "}" in expr_str:
            return {"pattern": "Set Modifier Matrix"}
        return {"pattern": "Standard Aggregation"}

    def _match_schema_casing(self, table_name: str, field_name: str) -> tuple:
        """
        Cross-references the column and table names with the uploaded M Query 
        schema dictionary to correct mismatching casing on the fly.
        """
        corrected_table = table_name
        corrected_field = field_name
        
        if not self.schema_context:
            return corrected_table, corrected_field

        # 1. Attempt to resolve table name case-insensitively
        resolved_table_key = None
        for table_key in self.schema_context.keys():
            if table_key.lower() == table_name.lower():
                resolved_table_key = table_key
                corrected_table = table_key
                break

        # 2. Attempt to resolve column name within the matched table context
        if resolved_table_key:
            available_columns = self.schema_context[resolved_table_key].get("columns", [])
            for col in available_columns:
                if col.lower() == field_name.lower():
                    return corrected_table, col

        # 3. Global column lookup fallback if column belongs to a different schema block
        for table_key, table_val in self.schema_context.items():
            available_columns = table_val.get("columns", [])
            for col in available_columns:
                if col.lower() == field_name.lower():
                    return table_key, col

        return corrected_table, corrected_field

    def convert(self, qlik_expr: str, measure_table: str = "FactSales") -> str:
        """
        Main structural translation engine thread. Processes raw Qlik syntax tokens,
        extracts set operations, resolves schemas, and compiles target DAX strings.
        """
        raw_input = str(qlik_expr).strip()
        
        # 1. Parse outer aggregation framework boundaries
        agg_pattern = re.match(r"^(Sum|Count|Avg|Max|Min)\((.*)\)$", raw_input, re.IGNORECASE)
        if not agg_pattern:
            return f"-- PARSE EXCEPTION: Expressions must begin with an aggregation function. Core signature mismatch on: {raw_input}"
            
        qlik_agg = agg_pattern.group(1).upper()
        dax_agg = qlik_agg
        if dax_agg == "AVG":
            dax_agg = "AVERAGE"
            
        inner_body = agg_pattern.group(2).strip()
        
        # 2. Extract and translate DISTINCT modifiers
        if "distinct " in inner_body.lower():
            inner_body = re.sub(r"distinct\s+", "", inner_body, flags=re.IGNORECASE).strip()
            if dax_agg == "COUNT":
                dax_agg = "DISTINCTCOUNT"

        filter_arguments = []
        base_field_name = inner_body

        # 3. Tokenize and parse Set Analysis blocks: { ... }
        if "{" in inner_body and "}" in inner_body:
            start_bracket = inner_body.find("{")
            end_bracket = inner_body.rfind("}") + 1
            set_signature = inner_body[start_bracket:end_bracket]
            
            # Isolate the pure column reference field name outside the set parameters
            base_field_name = inner_body.replace(set_signature, "").strip()
            set_body = set_signature[1:-1].strip() # Strip out external curly brackets
            
            # Process global modifier identity marker: {1}
            if set_body == "1":
                actual_table, _ = self._match_schema_casing(measure_table, base_field_name)
                filter_arguments.append(f"REMOVEFILTERS('{actual_table}')")
                
            # Process modifier array lists inside angle brackets: < ... >
            elif set_body.startswith("<") and set_body.endswith(">"):
                modifiers_content = set_body[1:-1].strip()
                
                # Split rules into conditions while ignoring internal functional commas
                parsed_conditions = []
                temporary_condition = []
                parenthesis_depth = 0
                curly_depth = 0
                
                for character in modifiers_content:
                    if character == '(': parenthesis_depth += 1
                    elif character == ')': parenthesis_depth -= 1
                    elif character == '{': curly_depth += 1
                    elif character == '}': curly_depth -= 1
                    elif character == ',' and parenthesis_depth == 0 and curly_depth == 0:
                        parsed_conditions.append("".join(temporary_condition).strip())
                        temporary_condition = []
                        continue
                    temporary_condition.append(character)
                if temporary_condition:
                    parsed_conditions.append("".join(temporary_condition).strip())

                # Process every extracted condition row
                for assignment in parsed_conditions:
                    if not assignment or "=" not in assignment:
                        continue
                        
                    filter_field, filter_value = assignment.split("=", 1)
                    filter_field = filter_field.strip()
                    filter_value = filter_value.strip()
                    
                    # Detect subtraction exclusion operators (e.g., Field=-{Value})
                    is_exclusion_modifier = False
                    if filter_field.endswith("-"):
                        is_exclusion_modifier = True
                        filter_field = filter_field.rstrip("-").strip()
                    elif filter_value.startswith("-"):
                        is_exclusion_modifier = True
                        filter_value = filter_value.lstrip("-").strip()
                        
                    # Correct field and table naming context based on active schema layouts
                    context_table, context_field = self._match_schema_casing(measure_table, filter_field)
                    target_column_reference = f"'{context_table}'[{context_field}]"
                    
                    # Parse Qlik element selection matching functions: P( ... )
                    if "P(" in filter_value.upper():
                        element_match = re.search(r"P\(\s*\{\s*<\s*([^>]+)\s*>\s*\}\s*([^)]+)\s*\)", filter_value, re.IGNORECASE)
                        if element_match:
                            p_modifier_body = element_match.group(1).strip()
                            p_target_field = element_match.group(2).strip()
                            
                            if "=" in p_modifier_body:
                                pf_raw, pv_raw = p_modifier_body.split("=", 1)
                                pv_clean = pv_raw.strip().strip("{}'\"")
                                p_table, p_field = self._match_schema_casing(measure_table, p_target_field)
                                pf_table, pf_field = self._match_schema_casing(measure_table, pf_raw.strip())
                                
                                filter_arguments.append(
                                    f"KEEPFILTERS(CALCULATETABLE(VALUES('{p_table}'[{p_field}]), '{pf_table}'[{pf_field}] = \"{pv_clean}\"))"
                                )
                        else:
                            filter_arguments.append(f"KEEPFILTERS(CALCULATETABLE(VALUES('{target_column_reference}')))")
                    
                    else:
                        # Process alphanumeric string or conditional value variables
                        cleaned_value = filter_value.strip("{}'\"")
                        comparison_operator_match = re.match(r"^([><=]+)(.*)$", cleaned_value)
                        
                        if comparison_operator_match:
                            operator_symbol = comparison_operator_match.group(1)
                            numerical_literal = comparison_operator_match.group(2).strip().strip("'\"")
                            filter_arguments.append(f"{target_column_reference} {operator_symbol} {numerical_literal}")
                        else:
                            if is_exclusion_modifier:
                                if cleaned_value.isdigit():
                                    filter_arguments.append(f"{target_column_reference} <> {cleaned_value}")
                                else:
                                    filter_arguments.append(f"{target_column_reference} <> \"{cleaned_value}\"")
                            else:
                                if cleaned_value.isdigit():
                                    filter_arguments.append(f"{target_column_reference} = {cleaned_value}")
                                else:
                                    filter_arguments.append(f"{target_column_reference} = \"{cleaned_value}\"")

        # 4. Correct schema casing paths for the core aggregation target column reference
        final_table, final_field = self._match_schema_casing(measure_table, base_field_name)
        
        # 5. Route through complex native Time Intelligence evaluation layers if needed
        if "yearstart" in raw_input.lower() or "today" in raw_input.lower():
            # Dynamically look up and locate your true model calendar tracking date key
            _, date_field = self._match_schema_casing(final_table, "OrderDate")
            return f"CALCULATE({dax_agg}('{final_table}'[{final_field}]), DATESYTD('{final_table}'[{date_field}]))"

        # 6. Assemble and compile final DAX output formula string
        core_aggregation_string = f"{dax_agg}('{final_table}'[{final_field}])"
        
        if filter_arguments:
            return f"CALCULATE({core_aggregation_string}, {', '.join(filter_arguments)})"
        else:
            return core_aggregation_string