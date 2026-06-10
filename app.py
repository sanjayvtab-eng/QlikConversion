import sys
import os
import importlib

# Ensure repository root is on sys.path (some platforms change working dir)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Try to import the package and create top-level module aliases so
# imports like `from parser.qlik_parser import ...` still work if present
try:
    pkg = importlib.import_module("QlikToPowerBIConverter")
    try:
        sys.modules["parser"] = importlib.import_module("QlikToPowerBIConverter.parser")
    except Exception:
        pass
    try:
        sys.modules["agents"] = importlib.import_module("QlikToPowerBIConverter.agents")
    except Exception:
        pass
    try:
        sys.modules["generators"] = importlib.import_module("QlikToPowerBIConverter.generators")
    except Exception:
        pass
except Exception:
    pass

import json
import base64
import streamlit as st
import streamlit.components.v1 as components
from QlikToPowerBIConverter.agents.migration_agent import MigrationAgent
from QlikToPowerBIConverter.generators.m_generator import MGenerator

# Ensure uploads directories exist
base_dir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(base_dir, "uploads"), exist_ok=True)
os.makedirs(os.path.join(base_dir, "QlikToPowerBIConverter", "uploads"), exist_ok=True)

st.set_page_config(page_title="QlikToPowerBIConverter", page_icon="🔁", layout="wide")
st.title("QlikToPowerBIConverter")
st.caption("Upload a Qlik script (.qvs) to analyze ETL logic and generate Power Query M code.")

# ── Custom file uploader via HTML component ──────────────────────────────────
# Streamlit's built-in st.file_uploader does a PUT to /_stcore/upload_file/...
# which Cloudflare (sitting in front of Render) blocks with a 403.
# This component reads the file in-browser and sends the base64 content back
# through the Streamlit WebSocket (component value), bypassing the PUT entirely.

file_uploader_html = """
<style>
  body { margin: 0; font-family: sans-serif; }
  #drop-zone {
    border: 2px dashed #555;
    border-radius: 8px;
    padding: 32px 24px;
    text-align: center;
    color: #ccc;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
    background: #1e1e2e;
  }
  #drop-zone.dragover { border-color: #7c6af7; background: #2a2a3e; }
  #drop-zone.has-file { border-color: #4caf50; background: #1a2e1a; color: #90ee90; }
  #file-input { display: none; }
  #browse-btn {
    display: inline-block;
    margin-top: 10px;
    padding: 8px 20px;
    background: #4f46e5;
    color: white;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
  }
  #browse-btn:hover { background: #6366f1; }
  #status { margin-top: 8px; font-size: 13px; color: #aaa; }
</style>

<div id="drop-zone" onclick="document.getElementById('file-input').click()">
  <div>📂 Drag and drop file here, or</div>
  <div id="browse-btn">Browse files</div>
  <div style="font-size:12px; margin-top:8px; color:#888;">Limit 200MB per file • QVS, TXT</div>
  <div id="status"></div>
</div>
<input type="file" id="file-input" accept=".qvs,.txt">

<script>
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const status = document.getElementById('status');

  function handleFile(file) {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['qvs', 'txt'].includes(ext)) {
      status.textContent = '❌ Only .qvs or .txt files are supported.';
      return;
    }
    status.textContent = '⏳ Reading ' + file.name + '...';
    const reader = new FileReader();
    reader.onload = function(e) {
      const base64 = e.target.result.split(',')[1];
      dropZone.classList.add('has-file');
      dropZone.querySelector('div').textContent = '✅ ' + file.name;
      status.textContent = 'File ready — ' + (file.size / 1024).toFixed(1) + ' KB';
      // Send file data back to Streamlit via component value
      Streamlit.setComponentValue({
        name: file.name,
        size: file.size,
        content_b64: base64
      });
    };
    reader.onerror = function() {
      status.textContent = '❌ Failed to read file.';
    };
    reader.readAsDataURL(file);
  }

  fileInput.addEventListener('change', (e) => handleFile(e.target.files[0]));

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFile(e.dataTransfer.files[0]);
  });

  // Tell Streamlit component is ready
  Streamlit.setFrameHeight(160);
</script>
"""

file_data = components.html(file_uploader_html, height=170)

# ── Process uploaded file ────────────────────────────────────────────────────
if file_data and isinstance(file_data, dict) and file_data.get("content_b64"):
    file_bytes = base64.b64decode(file_data["content_b64"])
    filename = file_data["name"]
    raw_text = file_bytes.decode("utf-8", errors="ignore")

    st.success(f"Uploaded: {filename}")
    st.subheader("Uploaded script")
    st.code(raw_text, language="text")

    try:
        upload_path = os.path.join(base_dir, "uploads", filename)
        with open(upload_path, "wb") as f:
            f.write(file_bytes)
        pkg_upload_path = os.path.join(base_dir, "QlikToPowerBIConverter", "uploads", filename)
        with open(pkg_upload_path, "wb") as f:
            f.write(file_bytes)
        print(f"[UPLOAD] Saved file to: {upload_path} ({os.path.getsize(upload_path)} bytes)")
    except Exception as ex:
        print(f"[UPLOAD] Error saving uploaded file: {ex}")

    if st.button("Generate Power Query M"):
        try:
            agent = MigrationAgent(base_dir=".")
            generator = MGenerator()
            analysis = agent.analyze(raw_text)
            metadata = analysis.get("metadata", {})
            generated_m = generator.generate(analysis)

            st.subheader("1. Detected Tables")
            tables = metadata.get("tables", [])
            st.write(tables if tables else "No table declarations were found.")

            st.subheader("2. Detected ETL Operations")
            st.write("\n".join(f"- {item}" for item in analysis.get("operations", [])))

            st.subheader("3. Parsed Metadata (JSON)")
            st.json(metadata)

            st.subheader("4. Generated Power Query M Code")
            st.code(generated_m, language="m")

            st.subheader("5. Warnings and Unsupported Features")
            if analysis.get("warnings", []):
                for warning in analysis.get("warnings", []):
                    st.warning(warning)
            else:
                st.success("No unsupported features were flagged by the current rule set.")
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.exception(e)
else:
    st.info("Choose a .qvs or .txt file to begin.")