# auto_installer.py
# Detect common imports in a python file and attempt pip install
import re
import subprocess
import sys
from pathlib import Path

def detect_imports_from_file(path: Path):
    text = path.read_text(errors="ignore")
    imports = re.findall(r'^\s*(?:from|import)\s+([A-Za-z0-9_\.]+)', text, flags=re.M)
    # keep top-level package names
    pkgs = set([s.split(".")[0] for s in imports if s])
    # filter stdlib heuristically (small list)
    stdlib = {"os","sys","re","time","math","json","pathlib","subprocess","datetime","typing","itertools"}
    return [p for p in pkgs if p not in stdlib]

def detect_and_install_requirements(main_py_path, msg=None):
    p = Path(main_py_path)
    pkgs = detect_imports_from_file(p)
    if not pkgs:
        return []
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *pkgs], timeout=600)
        return pkgs
    except Exception as e:
        print("install error", e)
        return pkgs
