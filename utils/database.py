import json
import os
from datetime import datetime

DB_FILE = 'database.json'

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {'users': {}, 'projects': {}}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_user(user_id):
    db = load_db()
    return db['users'].get(str(user_id), {'premium': False, 'banned': False, 'projects': []})

def update_user(user_id, data):
    db = load_db()
    db['users'][str(user_id)] = {**get_user(user_id), **data}
    save_db(db)

def get_projects(user_id):
    return get_user(user_id)['projects']

def add_project(user_id, project_name, path):
    db = load_db()
    projects = db['projects']
    projects[f"{user_id}_{project_name}"] = {
        'user_id': user_id,
        'name': project_name,
        'path': path,
        'status': 'stopped',
        'pid': None,
        'uptime': 0,
        'last_run': None,
        'last_exit_code': None,
        'run_command': f'python3 main.py',
        'backups': []
    }
    db['users'][str(user_id)]['projects'].append(project_name)
    save_db(db)

def get_project(user_id, project_name):
    db = load_db()
    return db['projects'].get(f"{user_id}_{project_name}")

def update_project(user_id, project_name, data):
    db = load_db()
    key = f"{user_id}_{project_name}"
    if key in db['projects']:
        db['projects'][key].update(data)
        save_db(db)
  
