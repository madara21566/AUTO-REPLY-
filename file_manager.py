# file_manager.py
# FastAPI-based simple file manager with token-based login
import os
import json
import secrets
from pathlib import Path
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
import uvicorn

ROOT = Path(os.getenv("DISK_MOUNT", ".")).resolve()
USERS_DIR = ROOT / "users"
TOKENS_FILE = ROOT / "data" / "fm_tokens.json"
TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI()

def save_tokens(d):
    TOKENS_FILE.write_text(json.dumps(d))

def load_tokens():
    if TOKENS_FILE.exists():
        return json.loads(TOKENS_FILE.read_text())
    return {}

def create_token_for_user(user_id: int, lifetime_seconds: int = 3600) -> str:
    tokens = load_tokens()
    token = secrets.token_urlsafe(16)
    tokens[token] = {"uid": int(user_id), "expiry": int(time.time()) + lifetime_seconds}
    save_tokens(tokens)
    return token

def token_valid_for_user(token: str, user_id: int) -> bool:
    tokens = load_tokens()
    info = tokens.get(token)
    if not info:
        return False
    if info["uid"] != int(user_id):
        return False
    if int(time.time()) > info["expiry"]:
        # expired
        tokens.pop(token, None)
        save_tokens(tokens)
        return False
    return True

def filemanager_url_for(user_id: int, project: str, token: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}/fm?uid={user_id}&proj={project}&token={token}"

# Simple HTML UI (very basic)
@app.get("/fm", response_class=HTMLResponse)
def fm_index(uid: int, proj: str, token: str):
    if not token_valid_for_user(token, uid):
        return HTMLResponse("<h3>Invalid or expired token</h3>", status_code=403)
    base = USERS_DIR / str(uid) / proj
    if not base.exists():
        return HTMLResponse("<h3>Project not found</h3>")
    files = [p.name for p in base.iterdir() if p.is_file()]
    html = "<h2>File Manager</h2>"
    html += f"<p>User: {uid} | Project: {proj}</p><ul>"
    for f in files:
        html += f"<li>{f} - <a href='/fm/download?uid={uid}&proj={proj}&file={f}&token={token}'>Download</a> | <a href='/fm/edit?uid={uid}&proj={proj}&file={f}&token={token}'>Edit</a> | <a href='/fm/delete?uid={uid}&proj={proj}&file={f}&token={token}'>Delete</a></li>"
    html += "</ul>"
    html += f"""
    <form action="/fm/upload" enctype="multipart/form-data" method="post">
    <input type="hidden" name="uid" value="{uid}"><input type="hidden" name="proj" value="{proj}">
    <input type="file" name="file"/><input type="hidden" name="token" value="{token}">
    <input type="submit" value="Upload"/>
    </form>
    """
    return HTMLResponse(html)

@app.post("/fm/upload")
async def fm_upload(uid: int = Form(...), proj: str = Form(...), token: str = Form(...), file: UploadFile = File(...)):
    if not token_valid_for_user(token, uid):
        raise HTTPException(status_code=403, detail="Invalid token")
    base = USERS_DIR / str(uid) / proj
    base.mkdir(parents=True, exist_ok=True)
    dest = base / file.filename
    content = await file.read()
    dest.write_bytes(content)
    return RedirectResponse(f"/fm?uid={uid}&proj={proj}&token={token}", status_code=303)

@app.get("/fm/download")
def fm_download(uid: int, proj: str, file: str, token: str):
    if not token_valid_for_user(token, uid):
        raise HTTPException(status_code=403)
    p = USERS_DIR / str(uid) / proj / file
    if not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(p), filename=p.name)

@app.get("/fm/delete")
def fm_delete(uid: int, proj: str, file: str, token: str):
    if not token_valid_for_user(token, uid):
        raise HTTPException(status_code=403)
    p = USERS_DIR / str(uid) / proj / file
    if p.exists():
        p.unlink()
    return RedirectResponse(f"/fm?uid={uid}&proj={proj}&token={token}", status_code=303)

@app.get("/fm/edit", response_class=HTMLResponse)
def fm_edit(uid: int, proj: str, file: str, token: str):
    if not token_valid_for_user(token, uid):
        return HTMLResponse("<h3>Invalid token</h3>", status_code=403)
    p = USERS_DIR / str(uid) / proj / file
    if not p.exists():
        return HTMLResponse("<h3>File not found</h3>", status_code=404)
    content = p.read_text(errors="ignore")
    html = f"""
    <h2>Edit {file}</h2>
    <form method="post" action="/fm/save">
    <input type="hidden" name="uid" value="{uid}"><input type="hidden" name="proj" value="{proj}">
    <input type="hidden" name="file" value="{file}"><input type="hidden" name="token" value="{token}">
    <textarea name="content" rows="20" cols="80">{content}</textarea><br/>
    <input type="submit" value="Save"/>
    </form>
    """
    return HTMLResponse(html)

@app.post("/fm/save")
def fm_save(uid: int = Form(...), proj: str = Form(...), file: str = Form(...), token: str = Form(...), content: str = Form(...)):
    if not token_valid_for_user(token, uid):
        raise HTTPException(status_code=403)
    p = USERS_DIR / str(uid) / proj / file
    p.write_text(content)
    return RedirectResponse(f"/fm?uid={uid}&proj={proj}&token={token}", status_code=303)

if __name__ == "__main__":
    uvicorn.run("file_manager:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
