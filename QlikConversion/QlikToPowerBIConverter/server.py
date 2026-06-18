import os
import sys

# Ensure root directory is in python path
base_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(base_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.migration_agent import MigrationAgent
from generators.m_generator import MGenerator

app = FastAPI(title="Qlik To Power BI Converter API")

# Ensure static folder exists
os.makedirs("static", exist_ok=True)

# Mount the static directory to serve HTML/CSS/JS
app.mount("/static", StaticFiles(directory="static"), name="static")

import re

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        raw_text = content.decode("utf-8", errors="replace")

        patterns = [
            r'FROM\s+\[?([^\]\n;]+)',
            r'LOAD\s+.*?FROM\s+\[?([^\]\n;]+)'
        ]
        detected_sources = []
        for pattern in patterns:
            matches = re.findall(pattern, raw_text, flags=re.IGNORECASE | re.DOTALL)
            detected_sources.extend(matches)

        detected_sources = list(dict.fromkeys([x.strip().strip("'\"[]") for x in detected_sources if x.strip()]))

        return JSONResponse(content={
            "success": True,
            "raw_text": raw_text,
            "detected_sources": detected_sources
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

class GenerateRequest(BaseModel):
    raw_text: str
    file_mappings: dict
    platform_type: str = "Excel Workbook (.xlsx)"  # <-- NEW: Captured from UI Dropdown
    connection_details: str = ""                   # <-- NEW: Captured from UI Input Box

@app.post("/api/generate")
async def generate_m(req: GenerateRequest):
    try:
        agent = MigrationAgent(base_dir=".")
        generator = MGenerator()

        analysis = agent.analyze(req.raw_text)
        analysis["file_paths"] = req.file_mappings
        
        # --- NEW: Inject UI Source Platform Details into Context ---
        analysis["platform_type"] = req.platform_type
        analysis["connection_details"] = req.connection_details
        
        metadata = analysis.get("metadata", {})
        generated_m = generator.generate(analysis)
        per_table = generator.generate_per_table(analysis)

        # (Keep your extraction logic for clean schema metadata exactly as it is below...)
        formatted_schema = {}
        table_blocks = analysis.get("table_blocks", [])
        if isinstance(table_blocks, list) and len(table_blocks) > 0:
            for block in table_blocks:
                if not isinstance(block, dict): continue
                table_info = block.get("table", {})
                t_name = table_info.get("name") if isinstance(table_info, dict) else str(table_info)
                if not t_name: t_name = block.get("table_name", "UnknownTable")
                raw_cols = block.get("columns", [])
                clean_cols = [c.get("name").strip() if isinstance(c, dict) else str(c).strip() for c in raw_cols if c]
                formatted_schema[t_name] = {"columns": clean_cols}
        
        return JSONResponse(content={
            "success": True,
            "generated_m": generated_m,
            "per_table": per_table,
            "tables": metadata.get("tables", []),
            "table_blocks": table_blocks,
            "operations": analysis.get("operations", []),
            "warnings": analysis.get("warnings", []),
            "metadata": formatted_schema
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
@app.post("/api/dax/preview")
async def preview_dax(file: UploadFile = File(...)):
    try:
        import pandas as pd
        import io
        content = await file.read()
        file_ext = file.filename.split('.')[-1].lower()
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content), nrows=10)
        else:
            df = pd.read_excel(io.BytesIO(content), nrows=10)
        
        df = df.fillna("")
        columns = list(df.columns)
        rows = df.values.tolist()
        return JSONResponse(content={
            "success": True,
            "columns": columns,
            "rows": rows
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/dax/generate")
async def generate_dax(
    file: UploadFile = File(...),
    schema_context: UploadFile = File(None)
):
    try:
        import pandas as pd
        import io
        import json
        import time
        import re

        # Load schema context if provided
        schema_data = {}
        if schema_context:
            schema_content = await schema_context.read()
            schema_data = json.loads(schema_content.decode("utf-8", errors="replace"))

        # Read the Excel/CSV file
        content = await file.read()
        file_ext = file.filename.split('.')[-1].lower()
        
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))

        # Core conversion logic
        from converters.dax_converter import DaxConverter

        # ── BULLETPROOF PARSER LOADER ─────────────────────────────────────
        # "parser" is a shadowed name: CWD has its own parser/ package that
        # lacks set_analysis_parser, so a bare `from parser.set_analysis_parser`
        # import resolves to the wrong package and raises ModuleNotFoundError.
        # Load via absolute file path instead, exactly like app.py does.
        import importlib.util as _ilu
        _parser_path = os.path.join(parent_dir, "parser", "set_analysis_parser.py")
        if not os.path.exists(_parser_path):
            # Fallback: try the local parser/ sibling folder
            _parser_path = os.path.join(base_dir, "parser", "set_analysis_parser.py")
        _spec = _ilu.spec_from_file_location("_local_set_analysis_parser", _parser_path)
        _mod  = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        SetAnalysisParser = _mod.SetAnalysisParser
        # ─────────────────────────────────────────────────────────────────

        converter = DaxConverter()
        converter.parser = SetAnalysisParser()
        if hasattr(converter, "set_schema_context"):
            converter.set_schema_context(schema_data)

        # Candidate column names matching app.py
        EXPRESSION_COL_CANDIDATES = ["Expression", "SetAnalysis", "Set Analysis", "Qlik Expression", "QlikExpression", "Measure", "Formula"]
        TABLE_COL_CANDIDATES = ["MeasureTable", "Measure Table", "Table", "FactTable"]
        NAME_COL_CANDIDATES = ["Visual Title", "MeasureName", "Measure Name", "Name", "DAX Name"]

        col_lower_map = {c.lower(): c for c in df.columns}
        def find_col(candidates):
            for c in candidates:
                if c.lower() in col_lower_map:
                    return col_lower_map[c.lower()]
            return None

        expr_col  = find_col(EXPRESSION_COL_CANDIDATES)
        table_col = find_col(TABLE_COL_CANDIDATES)
        name_col  = find_col(NAME_COL_CANDIDATES)

        if not expr_col:
            raise ValueError("Auto-detect failed: Could not find an expression column in the mapping sheet.")

        dax_results = []
        validation_logs = []
        conversion_errors_count = 0

        for idx, row in df.iterrows():
            qlik_expression = str(row[expr_col]).strip()
            if not qlik_expression or qlik_expression.lower() == "nan":
                continue

            if table_col and table_col in row and str(row[table_col]).strip().lower() not in ("", "nan"):
                measure_table = str(row[table_col]).strip()
            else:
                measure_table = "FactSales"

            measure_name = f"Measure_Row_{idx + 1}"
            if name_col and name_col in row and str(row[name_col]).strip().lower() not in ("", "nan"):
                measure_name = str(row[name_col]).strip()

            start_time = time.time()
            row_errors, row_warnings = [], []

            try:
                dax_code_raw = converter.convert(qlik_expression, measure_table)
                if dax_code_raw.count("(") != dax_code_raw.count(")"):
                    row_errors.append("Syntax Error: Parenthesis mismatch.")
                
                dax_code = f"{measure_name} = {dax_code_raw}" if not dax_code_raw.startswith("-- ERROR") else dax_code_raw
                
                if schema_data:
                    extracted_tables = re.findall(r"'([^']+)'", dax_code_raw)
                    for tbl in extracted_tables:
                        if tbl not in schema_data:
                            row_warnings.append(f"Schema Warning: Table '{tbl}' not found.")
                            
            except Exception as conv_err:
                dax_code = f"-- ERROR: {conv_err}"
                row_errors.append(str(conv_err))
                conversion_errors_count += 1

            execution_time_ms = round((time.time() - start_time) * 1000, 2)
            try:
                parsed = converter.parser.parse(qlik_expression)
                pattern_detected = parsed.get('pattern', 'Complex/Unknown')
            except Exception:
                pattern_detected = "Complex Evaluation"

            dax_results.append({
                "Measure Name":    measure_name,
                "Target Table":    measure_table,
                "Qlik Expression": qlik_expression,
                "DAX Output":      dax_code,
                "Pattern Framework": pattern_detected,
                "Status":          "FAILED" if row_errors else "PASSED",
                "Execution (ms)":  execution_time_ms,
            })

            if row_errors or row_warnings:
                validation_logs.append({
                    "Row": idx + 1,
                    "Measure Name": measure_name,
                    "Validation Errors": "; ".join(row_errors) if row_errors else "None",
                    "Validation Warnings": "; ".join(row_warnings) if row_warnings else "None"
                })

        # Generate Excel package
        from io import BytesIO
        import base64
        
        excel_buf = BytesIO()
        with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
            pd.DataFrame(dax_results).to_excel(writer, sheet_name="Conversion Report", index=False)
            if validation_logs:
                pd.DataFrame(validation_logs).to_excel(writer, sheet_name="Validation Logs", index=False)
        excel_buf.seek(0)
        excel_b64 = base64.b64encode(excel_buf.read()).decode('utf-8')

        return JSONResponse(content={
            "success": True,
            "results": dax_results,
            "validation_logs": validation_logs,
            "conversion_errors_count": conversion_errors_count,
            "total_rows": len(dax_results),
            "excel_package": excel_b64
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

# Redirect root to /static/index.html
from fastapi.responses import RedirectResponse
@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)