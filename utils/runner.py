import subprocess
import psutil
import os
from datetime import datetime
from .database import get_project, update_project
from .auto_install import install_requirements

def run_script(user_id, project_name):
    project = get_project(user_id, project_name)
    if not project:
        return False
    path = project['path']
    os.chdir(path)
    install_requirements(path)
    proc = subprocess.Popen(['python3', 'main.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    update_project(user_id, project_name, {
        'status': 'running',
        'pid': proc.pid,
        'last_run': datetime.utcnow().isoformat(),
        'last_exit_code': None
    })
    return True

def stop_script(user_id, project_name):
    project = get_project(user_id, project_name)
    if project and project['pid']:
        try:
            psutil.Process(project['pid']).terminate()
            update_project(user_id, project_name, {'status': 'stopped', 'pid': None})
            return True
        except:
            pass
    return False

def restart_script(user_id, project_name):
    stop_script(user_id, project_name)
    return run_script(user_id, project_name)

def get_logs(user_id, project_name):
    project = get_project(user_id, project_name)
    if project and project['pid']:
        proc = psutil.Process(project['pid'])
        return proc.stdout.read().decode() + proc.stderr.read().decode()
    return "No logs available."
