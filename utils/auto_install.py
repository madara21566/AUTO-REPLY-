import os
import subprocess
import ast

def install_requirements(path):
    req_file = os.path.join(path, 'requirements.txt')
    if os.path.exists(req_file):
        subprocess.run(['pip', 'install', '-r', req_file])
    else:
        # Detect imports from main.py
        main_file = os.path.join(path, 'main.py')
        if os.path.exists(main_file):
            with open(main_file, 'r') as f:
                tree = ast.parse(f.read())
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split('.')[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module.split('.')[0] if node.module else '')
            for lib in imports:
                if lib and lib not in ['os', 'sys', 'json']:  # Skip builtins
                    subprocess.run(['pip', 'install', lib])
