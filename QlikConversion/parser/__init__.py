import sys
import os

# Dynamically calculate the path to 'QlikConversion' (one level up from this file)
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if root_path not in sys.path:
    sys.path.insert(0, root_path)