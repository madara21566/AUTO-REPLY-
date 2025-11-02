import shutil
import os
from datetime import datetime
from .database import get_project, update_project

def backup_project(user_id, project_name):
    project = get_project(user_id, project_name)
    if not project:
        return
    path = project['path']
    backup_dir = os.path.join(path, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'backup_{timestamp}.zip')
    shutil.make_archive(backup_path.replace('.zip', ''), 'zip', path)
    backups = project['backups']
    backups.append(backup_path)
    if len(backups) > 3:
        os.remove(backups.pop(0))
    update_project(user_id, project_name, {'backups': backups})
