"""Run a clean-account smoke test against a real Uvicorn HTTP listener."""
import argparse
import json
from urllib.request import Request, urlopen
import uuid

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000")
args = parser.parse_args()


def call(path, payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None if payload is None else json.dumps(payload).encode()
    with urlopen(Request(args.url.rstrip("/") + path, body, headers), timeout=15) as response:
        return json.load(response)


assert call("/health")["status"] == "ok"
credentials = {"email": f"smoke-{uuid.uuid4().hex}@example.test", "password": uuid.uuid4().hex}
workspace = call("/api/register", credentials)["workspace_id"]
token = call("/api/login", credentials)["access_token"]
prefix = f"/api/workspaces/{workspace}"
assert len(call(prefix + "/demo", {}, token)) == 3
answer = call(prefix + "/chat", {"question": "How many vacation days do employees receive?"}, token)
assert answer["status"] == "grounded" and "20 vacation days" in answer["answer"]
citation = answer["citations"][0]
excerpt = call(prefix + f'/chunks/{citation["id"]}', token=token)
assert citation["quote"] in excerpt["text"]
assert call("/api/logout", {}, token)["signed_out"]
print("HTTP smoke passed: health, registration, login, ingestion, answer, citation and logout.")
