"""Toy evaluation of lexical ranking on three synthetic sample documents."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from retrieval import answer, chunks, parse, rank

rows = []
for document_id, path in enumerate(sorted((root / "samples").glob("*.md")), 1):
    for section, body, _ in chunks(parse(".md", path.read_bytes())):
        rows.append({"id": len(rows) + 1, "document_id": document_id, "title": path.name,
                     "section": section, "text": body})

cases = [
    ("How many vacation days do employees receive?", "hr-policy.md", "Vacation days"),
    ("What is the procedure for critical incident escalation?", "engineering-runbook.md", "Incident escalation"),
    ("Who verifies identity before account recovery?", "support-guide.md", "Account recovery"),
    ("Where are Martian mineral deposits?", None, None),
]
for mode in ("keyword", "vector", "hybrid"):
    correct = 0
    for question, expected_title, expected_section in cases[:3]:
        results = rank(rows, question, mode, 3)
        correct += bool(results and (results[0]["title"], results[0]["section"]) == (expected_title, expected_section))
    print(f"{mode} retrieval precision@1: {correct}/3")
    assert correct == 3
result = answer(cases[3][0], rank(rows, cases[3][0], "hybrid", 3))
assert result["status"] == "insufficient_evidence"
print("Out-of-corpus abstention: 1/1")
