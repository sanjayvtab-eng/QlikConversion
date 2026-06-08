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

from QlikToPowerBIConverter import app as qlik_app

if __name__ == "__main__":
    pass
