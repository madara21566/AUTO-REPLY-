from flask import Flask, render_template, request, redirect, url_for, send_file
import os
from utils.database import get_project

app = Flask(__name__)

@app.route('/file_manager/<int:user_id>/<project_name>')
def file_manager(user_id, project_name):
    project = get_project(user_id, project_name)
    if not project:
        return "Project not found", 404
    path = project['path']
    files = os.listdir(path) if os.path.exists(path) else []
    return render_template('file_manager.html', files=files, path=path, user_id=user_id, project_name=project_name)

# Add routes for edit, delete, upload, download (implement as needed)
