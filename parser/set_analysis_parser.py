# parser/set_analysis_parser.py

import re


class SetAnalysisParser:

    def parse(self, expression):

        result = {
            "aggregation": None,
            "measure": None,
            "filters": [],
            "pattern": "STANDARD"
        }

        # -------------------------
        # Pattern Detection
        # -------------------------

        if "MonthStart" in expression:
            result["pattern"] = "MTD"

        elif "YearStart" in expression:
            result["pattern"] = "YTD"

        elif "QuarterStart" in expression:
            result["pattern"] = "QTD"

        elif "AddMonths" in expression:
            result["pattern"] = "MOM"

        elif "AddYears" in expression:
            result["pattern"] = "YOY"

        elif "{1}" in expression:
            result["pattern"] = "IGNORE_SELECTION"

        elif "{$}" in expression:
            result["pattern"] = "CURRENT_SELECTION"

        elif "DISTINCT" in expression.upper():
            result["pattern"] = "DISTINCT"

        elif "TOTAL" in expression.upper():
            result["pattern"] = "TOTAL"

        elif "P(" in expression.upper():
            result["pattern"] = "P_FUNCTION"

        elif "E(" in expression.upper():
            result["pattern"] = "E_FUNCTION"

        # -------------------------
        # Aggregation
        # -------------------------

        agg = re.search(
            r"(Sum|Count|Avg|Min|Max)",
            expression,
            re.IGNORECASE
        )

        if agg:
            result["aggregation"] = agg.group(1)

        # -------------------------
        # DISTINCT COUNT
        # -------------------------

        distinct_match = re.search(
            r"Count\s*\(\s*DISTINCT\s+([A-Za-z_][A-Za-z0-9_]*)\s*\)",
            expression,
            re.IGNORECASE
        )

        if distinct_match:

            result["aggregation"] = "DistinctCount"
            result["measure"] = distinct_match.group(1)

            return result

        # -------------------------
        # Measure Detection
        # -------------------------

        measure_match = re.search(
            r"\}\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)$",
            expression.strip()
        )

        if measure_match:

            result["measure"] = measure_match.group(1)

        else:

            agg_match = re.search(
                r"(Sum|Count|Avg|Min|Max)\s*\((.*)\)",
                expression,
                re.IGNORECASE
            )

            if agg_match:

                inner = agg_match.group(2)

                fields = re.findall(
                    r"[A-Za-z_][A-Za-z0-9_]*",
                    inner
                )

                ignore_words = {
                    "Date",
                    "Today",
                    "MonthStart",
                    "MonthEnd",
                    "AddMonths",
                    "YearStart",
                    "YearEnd",
                    "AddYears",
                    "QuarterStart",
                    "QuarterEnd",
                    "Sales",
                    "TOTAL",
                    "DISTINCT"
                }

                candidates = [
                    f for f in fields
                    if f not in ignore_words
                ]

                if candidates:
                    result["measure"] = candidates[-1]

        # -------------------------
        # Filters
        # -------------------------

        filters = re.findall(
            r"(\w+)\s*=\s*\{([^}]*)\}",
            expression
        )

        parsed_filters = []

        for field, value in filters:

            operator = "="

            if value.startswith(">="):
                operator = ">="

            elif value.startswith("<="):
                operator = "<="

            elif value.startswith(">"):
                operator = ">"

            elif value.startswith("<"):
                operator = "<"

            elif value.startswith("-"):
                operator = "<>"

                value = value.replace("-", "")

            parsed_filters.append(
                {
                    "field": field,
                    "operator": operator,
                    "value": value
                }
            )

        result["filters"] = parsed_filters

        return result