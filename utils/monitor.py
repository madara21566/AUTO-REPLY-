import psutil
from datetime import datetime
from .database import get_project, update_project

def update_uptime(user_id, project_name):
    project = get_project(user_id, project_name)
    if project and project['status'] == 'running' and project['pid']:
        try:
            proc = psutil.Process(project['pid'])
            uptime = (datetime.utcnow() - datetime.fromisoformat(project['last_run'])).total_seconds()
            update_project(user_id, project_name, {'uptime': uptime})
        except:
            update_project(user_id, project_name, {'status': 'stopped', 'pid': None})
