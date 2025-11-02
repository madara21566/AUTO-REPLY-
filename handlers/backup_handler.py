import asyncio
from utils.database import load_db
from utils.backup import backup_project

def register(app: Client):
    pass  # Backup loop is in main.py

async def backup_loop():
    while True:
        db = load_db()
        for key, project in db['projects'].items():
            user_id, project_name = key.split('_', 1)
            backup_project(int(user_id), project_name)
        await asyncio.sleep(600)  # 10 minutes
                                              
