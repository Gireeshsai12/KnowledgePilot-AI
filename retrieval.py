"""Parsing and CPU-only retrieval helpers."""
import csv
import io
import math
import re
from collections import Counter
from html.parser import HTMLParser
from zipfile import ZipFile

from docx import Document
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer

MAX_TEXT = 300_000
WORDS = re.compile(r"[^\W_]+", re.UNICODE)
STOP = set("the a an is are was be to for and or of on in how what where when can i my we our do does me tell about please with who which should".split())


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.hidden += 1
        elif tag in {"p", "div", "br", "h1", "h2", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def parse(extension, raw):
    if extension == ".pdf":
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted or len(reader.pages) > 100:
            raise ValueError("Use an unencrypted PDF with at most 100 pages.")
        sections = []
        total = 0
        for index, page in enumerate(reader.pages, 1):
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > 5_000_000:
                raise ValueError("PDF page content is too large.")
            content = page.extract_text() or ""
            total += len(content)
            if total > MAX_TEXT:
                raise ValueError("Extracted text is too large.")
            sections.append((f"Page {index}", content))
    elif extension == ".docx":
        with ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 500 or sum(item.file_size for item in entries) > 12_000_000:
                raise ValueError("DOCX archive exceeds extraction limits.")
        document = Document(io.BytesIO(raw))
        sections = []
        heading, paragraphs = "Document", []
        for paragraph in document.paragraphs:
            if paragraph.style.name.startswith("Heading"):
                sections.append((heading, "\n".join(paragraphs)))
                heading, paragraphs = paragraph.text[:160], []
            else:
                paragraphs.append(paragraph.text)
        sections.append((heading, "\n".join(paragraphs)))
        for index, table in enumerate(document.tables, 1):
            sections.append((f"Table {index}", "\n".join(
                " | ".join(cell.text for cell in row.cells) for row in table.rows
            )))
    else:
        content = raw.decode("utf-8-sig")
        if len(content) > MAX_TEXT:
            raise ValueError("Document text is too large.")
        if extension == ".html":
            parser = VisibleText()
            parser.feed(content)
            content = "".join(parser.parts)
        if extension == ".csv":
            content = "\n".join(" | ".join(row) for row in csv.reader(io.StringIO(content), strict=True))
        if extension == ".md":
            sections = []
            heading, lines = "Document", []
            for line in content.splitlines():
                if re.match(r"^#{1,6}\s+", line):
                    sections.append((heading, "\n".join(lines)))
                    heading, lines = line.lstrip("# ").strip()[:160], []
                else:
                    lines.append(line)
            sections.append((heading, "\n".join(lines)))
        else:
            sections = [("Document", content)]
    if sum(len(content) for _, content in sections) > MAX_TEXT:
        raise ValueError("Extracted text is too large.")
    return sections


def chunks(sections, strategy="heading", size=120, overlap=20):
    if not 0 <= overlap < size:
        raise ValueError("Overlap must be smaller than chunk size.")
    if strategy == "fixed":
        sections = [("Document", "\n".join(body for _, body in sections))]
    for section, body in sections:
        words = body.split()
        start = 0
        while start < len(words):
            end = min(start + size, len(words))
            if strategy == "recursive" and end < len(words):
                for candidate in range(end, start + max(overlap + 1, size // 2), -1):
                    if words[candidate - 1].endswith((".", "!", "?", ";")):
                        end = candidate
                        break
            yield section, " ".join(words[start:end]), end - start
            if end == len(words):
                break
            start = end - overlap


def terms(value):
    return [word.lower() for word in WORDS.findall(value) if word.lower() not in STOP]


def rank(rows, question, mode, limit):
    if not rows:
        return []
    query = set(terms(question))
    if not query or not any(terms(row["text"]) for row in rows):
        return []
    counts = [Counter(terms(row["text"])) for row in rows]
    keywords = [sum(math.log1p(count[token]) for token in query) / len(query) for count in counts]
    vectors = TfidfVectorizer(analyzer=terms, sublinear_tf=True)
    matrix = vectors.fit_transform(row["text"] for row in rows)
    scores = (matrix @ vectors.transform([question]).T).toarray().ravel()
    orders = [sorted((i for i, score in enumerate(values) if score > 0), key=lambda i: -values[i])
              for values in (keywords, scores)]
    if mode == "keyword":
        ordered, relevance = orders[0], keywords
    elif mode == "vector":
        ordered, relevance = orders[1], scores
    else:
        relevance = [0.0] * len(rows)
        for order in orders:
            for index, item in enumerate(order, 1):
                relevance[item] += 1 / (60 + index)
        ordered = sorted((i for i, score in enumerate(relevance) if score), key=lambda i: -relevance[i])
    return [dict(rows[index], score=round(float(relevance[index]), 6)) for index in ordered[:limit]]


def answer(question, results):
    query = set(terms(question))
    candidates = []
    for index, row in enumerate(results, 1):
        for sentence in re.split(r"(?<=[.!?])\s+", row["text"]):
            overlap = len(query.intersection(terms(sentence)))
            if overlap >= min(2, len(query)) and overlap:
                candidates.append((overlap, index, sentence))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    evidence = []
    seen = set()
    for _, index, sentence in candidates:
        if sentence in seen:
            continue
        seen.add(sentence)
        row = results[index - 1]
        evidence.append({"citation": len(evidence) + 1, "quote": sentence[:600],
                         **{key: row[key] for key in ("id", "document_id", "title", "section")}})
        if len(evidence) == 3:
            break
    return {"mode": "extractive", "status": "grounded" if evidence else "insufficient_evidence",
            "answer": "\n".join(f'{item["quote"]} [{item["citation"]}]' for item in evidence)
            or "I could not find sufficient evidence in the selected workspace.",
            "citations": evidence}
