"""KnowledgePilot local application."""
import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
import secrets
import sqlite3
import time

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from retrieval import answer, chunks, parse, rank

ROOT = Path(__file__).resolve().parent
MAX_UPLOAD = 2_000_000
EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".html"}
logger = logging.getLogger("knowledgepilot")
bearer = HTTPBearer(auto_error=False)


def connect():
    path = Path(os.getenv("KP_DB", str(ROOT / "data" / "knowledgepilot.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def database():
    db = connect()
    try:
        with db:
            yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app):
    db = connect()
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript((ROOT / "schema.sql").read_text())
    finally:
        db.close()
    yield


app = FastAPI(title="KnowledgePilot AI", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.middleware("http")
async def response_metadata(request, call_next):
    start = time.monotonic()
    request_id = secrets.token_hex(8)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    logger.info(json.dumps({"request_id": request_id, "method": request.method,
                            "status": response.status_code, "ms": round((time.monotonic() - start) * 1000)}))
    return response


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=10, max_length=128)


class Workspace(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class Member(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: str = Field(pattern="^(editor|viewer)$")


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=6, ge=1, le=15)
    document_id: int | None = None


class Comparison(BaseModel):
    first: int
    second: int
    topic: str = Field(min_length=2, max_length=300)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def current_session(auth: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(database)):
    if auth and len(auth.credentials) < 256:
        token_hash = digest(auth.credentials.encode())
        session = db.execute(
            "SELECT * FROM sessions WHERE digest=? AND expires>?", (token_hash, int(time.time()))
        ).fetchone()
        if session:
            return session
    raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})


def permission(db, workspace, session, roles=None):
    member = db.execute("SELECT role FROM members WHERE workspace_id=? AND user_id=?",
                        (workspace, session["user_id"])).fetchone()
    if member is None:
        raise HTTPException(404, "Workspace not found.")
    if roles and member["role"] not in roles:
        raise HTTPException(403, "Your workspace role does not allow this action.")


def audit(db, workspace, session, action):
    db.execute("INSERT INTO audit(workspace_id,user_id,action) VALUES(?,?,?)",
               (workspace, session["user_id"], action))


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "static" / "index.html", headers={
        "Content-Security-Policy": "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    })


@app.get("/health")
def health(db=Depends(database)):
    db.execute("SELECT 1")
    return {"status": "ok", "index": "local_tfidf", "generation": "extractive"}


@app.post("/api/register", status_code=201)
def register(payload: Credentials, db=Depends(database)):
    salt = secrets.token_hex(16)
    encoded = f"{salt}:{password_hash(payload.password, salt)}"
    try:
        user_id = db.execute("INSERT INTO users(email,password) VALUES(?,?)",
                             (payload.email.lower(), encoded)).lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account already exists for this address.") from None
    workspace = db.execute("INSERT INTO workspaces(name) VALUES(?)", ("My knowledge base",)).lastrowid
    db.execute("INSERT INTO members VALUES(?,?,?)", (workspace, user_id, "owner"))
    db.commit()
    return {"workspace_id": workspace}


@app.post("/api/login")
def login(payload: Credentials, db=Depends(database)):
    user = db.execute("SELECT * FROM users WHERE email=?", (payload.email.lower(),)).fetchone()
    salt, expected = user["password"].split(":") if user else ("0" * 32, "0" * 128)
    actual = password_hash(payload.password, salt)
    if not (hmac.compare_digest(actual, expected) and user):
        raise HTTPException(401, "Invalid credentials.")
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    db.execute("DELETE FROM sessions WHERE expires<=?", (now,))
    db.execute("INSERT INTO sessions VALUES(?,?,?)", (digest(token.encode()), user["id"], now + 3600))
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


@app.post("/api/logout")
def logout(session=Depends(current_session), db=Depends(database)):
    db.execute("DELETE FROM sessions WHERE digest=?", (session["digest"],))
    db.commit()
    return {"signed_out": True}


@app.get("/api/workspaces")
def workspaces(session=Depends(current_session), db=Depends(database)):
    return db.execute("SELECT w.id,w.name,m.role FROM workspaces w JOIN members m "
                      "ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.id", (session["user_id"],)).fetchall()


@app.post("/api/workspaces", status_code=201)
def create_workspace(payload: Workspace, session=Depends(current_session), db=Depends(database)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Enter a workspace name.")
    workspace = db.execute("INSERT INTO workspaces(name) VALUES(?)", (name,)).lastrowid
    db.execute("INSERT INTO members VALUES(?,?,?)", (workspace, session["user_id"], "owner"))
    db.commit()
    return {"id": workspace, "name": name, "role": "owner"}


@app.put("/api/workspaces/{workspace}/members")
def set_member(workspace: int, payload: Member, session=Depends(current_session), db=Depends(database)):
    permission(db, workspace, session, {"owner"})
    user = db.execute("SELECT id FROM users WHERE email=?", (payload.email.lower(),)).fetchone()
    if user is None:
        raise HTTPException(404, "Account not found.")
    if user["id"] == session["user_id"]:
        raise HTTPException(409, "The owner role cannot be changed here.")
    db.execute("INSERT INTO members VALUES(?,?,?) ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=excluded.role",
               (workspace, user["id"], payload.role))
    audit(db, workspace, session, "membership_updated")
    db.commit()
    return {"role": payload.role}


def ingest(db, workspace, name, raw, strategy):
    title = name.replace("\\", "/").rsplit("/", 1)[-1]
    if not title or len(title) > 180 or any(ord(char) < 32 for char in title):
        raise HTTPException(400, "Invalid filename.")
    extension = Path(title).suffix.lower()
    if extension not in EXTENSIONS:
        raise HTTPException(415, "Use PDF, DOCX, TXT, Markdown, CSV, or HTML.")
    if not raw:
        raise HTTPException(422, "The document is empty.")
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "The document exceeds 2 MB.")
    checksum = digest(raw)
    existing = db.execute("SELECT id FROM documents WHERE workspace_id=? AND digest=?",
                          (workspace, checksum)).fetchone()
    if existing:
        return {"id": existing["id"], "status": "duplicate"}
    try:
        records = list(chunks(parse(extension, raw), strategy))
    except Exception as exc:
        logger.info("Document parser rejected input (%s)", type(exc).__name__)
        raise HTTPException(422, "The document could not be parsed within the supported limits.") from None
    if not records:
        raise HTTPException(422, "No extractable text found. Image-only PDF requires OCR.")
    cursor = db.execute("INSERT INTO documents(workspace_id,title,digest,extension,raw) VALUES(?,?,?,?,?) "
                        "ON CONFLICT(workspace_id,digest) DO NOTHING", (workspace, title, checksum, extension, raw))
    if cursor.rowcount == 0:
        existing = db.execute("SELECT id FROM documents WHERE workspace_id=? AND digest=?",
                              (workspace, checksum)).fetchone()
        return {"id": existing["id"], "status": "duplicate"}
    document = cursor.lastrowid
    db.executemany("INSERT INTO chunks(document_id,ordinal,section,text,words) VALUES(?,?,?,?,?)",
                   ((document, ordinal, *record) for ordinal, record in enumerate(records)))
    return {"id": document, "status": "indexed", "chunks": len(records)}


@app.post("/api/workspaces/{workspace}/documents")
def upload(workspace: int, file: UploadFile = File(...), strategy: str = Query("heading", pattern="^(heading|fixed|recursive)$"),
           session=Depends(current_session), db=Depends(database)):
    permission(db, workspace, session, {"owner", "editor"})
    result = ingest(db, workspace, file.filename or "", file.file.read(MAX_UPLOAD + 1), strategy)
    audit(db, workspace, session, "document_" + result["status"])
    db.commit()
    return result


@app.post("/api/workspaces/{workspace}/demo")
def demo(workspace: int, session=Depends(current_session), db=Depends(database)):
    permission(db, workspace, session, {"owner", "editor"})
    results = [ingest(db, workspace, path.name, path.read_bytes(), "heading")
               for path in sorted((ROOT / "samples").glob("*.md"))]
    audit(db, workspace, session, "demo_loaded")
    db.commit()
    return results


@app.get("/api/workspaces/{workspace}/documents")
def documents(workspace: int, session=Depends(current_session), db=Depends(database)):
    permission(db, workspace, session)
    return db.execute("SELECT d.id,d.title,d.created_at,COUNT(c.id) AS chunks FROM documents d "
                      "LEFT JOIN chunks c ON c.document_id=d.id WHERE d.workspace_id=? "
                      "GROUP BY d.id ORDER BY d.id DESC", (workspace,)).fetchall()


@app.delete("/api/workspaces/{workspace}/documents/{document}")
def remove(workspace: int, document: int, session=Depends(current_session), db=Depends(database)):
    permission(db, workspace, session, {"owner", "editor"})
    if not db.execute("DELETE FROM documents WHERE workspace_id=? AND id=?", (workspace, document)).rowcount:
        raise HTTPException(404, "Document not found.")
    audit(db, workspace, session, "document_deleted")
    db.commit()
    return {"deleted": True}


def corpus(db, workspace, document=None):
    query = ("SELECT c.id,c.document_id,c.section,c.text,d.title FROM chunks c "
             "JOIN documents d ON d.id=c.document_id WHERE d.workspace_id=?")
    args = [workspace]
    if document is not None:
        query += " AND d.id=?"
        args.append(document)
    return db.execute(query + " ORDER BY c.id", args).fetchall()


@app.get("/api/workspaces/{workspace}/chunks/{chunk}")
def preview(workspace: int, chunk: int, session=Depends(current_session), db=Depends(database)):
    permission(db, workspace, session)
    row = db.execute("SELECT c.id,c.document_id,c.section,c.text,d.title FROM chunks c "
                     "JOIN documents d ON d.id=c.document_id WHERE d.workspace_id=? AND c.id=?",
                     (workspace, chunk)).fetchone()
    if not row:
        raise HTTPException(404, "Citation not found.")
    return dict(row)


@app.get("/api/workspaces/{workspace}/search")
def search(workspace: int, q: str = Query(min_length=2,max_length=500),
           mode: str = Query("hybrid", pattern="^(hybrid|keyword|vector)$"),
           top_k: int = Query(6, ge=1, le=15), document_id: int | None = None,
           session=Depends(current_session), db=Depends(database)):
    permission(db, workspace, session)
    return rank(corpus(db, workspace, document_id), q, mode, top_k)


def chat_response(db, workspace, session, payload):
    permission(db, workspace, session)
    result = answer(payload.question, rank(corpus(db, workspace, payload.document_id),
                                          payload.question, "hybrid", payload.top_k))
    db.execute("INSERT INTO messages(workspace_id,user_id,question,response) VALUES(?,?,?,?)",
               (workspace, session["user_id"], payload.question, json.dumps(result)))
    db.commit()
    return result


@app.post("/api/workspaces/{workspace}/chat")
def chat(workspace: int, payload: Question, session=Depends(current_session), db=Depends(database)):
    return chat_response(db, workspace, session, payload)


@app.post("/api/workspaces/{workspace}/chat/stream")
def stream(workspace: int, payload: Question, session=Depends(current_session), db=Depends(database)):
    result = chat_response(db, workspace, session, payload)

    def events():
        for line in result["answer"].splitlines():
            yield f"event: excerpt\ndata: {json.dumps(line)}\n\n"
        yield f"event: result\ndata: {json.dumps(result)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/workspaces/{workspace}/history")
def history(workspace: int, session=Depends(current_session), db=Depends(database)):
    permission(db, workspace, session)
    rows = db.execute("SELECT question,response,created_at FROM messages WHERE workspace_id=? AND user_id=? "
                      "ORDER BY id DESC LIMIT 30", (workspace, session["user_id"])).fetchall()
    return [dict(row, response=json.loads(row["response"])) for row in rows]


@app.post("/api/workspaces/{workspace}/compare")
def compare(workspace: int, payload: Comparison, session=Depends(current_session), db=Depends(database)):
    permission(db, workspace, session)
    if payload.first == payload.second:
        raise HTTPException(422, "Select two different documents.")
    results = []
    for document in (payload.first, payload.second):
        rows = corpus(db, workspace, document)
        if not rows:
            raise HTTPException(404, "Document not found.")
        result = answer(payload.topic, rank(rows, payload.topic, "hybrid", 4))
        results.append({"document_id": document, "title": rows[0]["title"], **result})
    audit(db, workspace, session, "comparison_executed")
    db.commit()
    return {"workflow": "document_comparison", "documents": results}
