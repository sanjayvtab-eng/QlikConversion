# converters/dax_converter_copy.py

# "parser" is shadowed by the project's own parser/ package — use absolute-path
# loading to avoid ModuleNotFoundError on 'parser.set_analysis_parser'.
import os, importlib.util as _ilu

_base = os.path.abspath(os.path.dirname(__file__))
_parser_path = os.path.join(_base, "..", "parser", "set_analysis_parser.py")
_parser_path = os.path.normpath(_parser_path)
_spec = _ilu.spec_from_file_location("_local_set_analysis_parser", _parser_path)
_mod  = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SetAnalysisParser = _mod.SetAnalysisParser


class DaxConverter:

    def __init__(self):
        self.parser = SetAnalysisParser()

    def convert(self, expression):

        parsed = self.parser.parse(expression)

        agg = parsed.get("aggregation")
        measure = parsed.get("measure")

        if not agg:
            return f"-- Unable to detect aggregation: {expression}"

        if not measure:
            return f"-- Unable to detect measure: {expression}"

        agg_map = {
            "Sum": "SUM",
            "Count": "COUNT",
            "Avg": "AVERAGE",
            "Min": "MIN",
            "Max": "MAX"
        }

        dax = "CALCULATE(\n"

        dax += (
            f"    {agg_map.get(agg, agg.upper())}"
            f"(Sales[{measure}])"
        )

        for field, value in parsed["filters"]:

            value = value.replace("'", "")
            value = value.replace('"', "")

            dax += (
                f",\n    Sales[{field}] = "
                f"\"{value}\""
            )

        dax += "\n)"

        return dax