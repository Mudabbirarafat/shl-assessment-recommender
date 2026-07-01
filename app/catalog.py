import json
import math
import os
import re
from collections import Counter
import token
from typing import List, Dict, Any, Optional
from .semantic_search import build as build_semantic
from .semantic_search import search as semantic_search

# from litellm import query
# from litellm import query
import numpy as np

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "catalog_full.json",
)
TEST_TYPE_LABELS = {
    "A": "Ability & Aptitude",
    "B": "Biodata & Situational Judgement",
    "C": "Competencies",
    "D": "Development & 360",
    "E": "Assessment Exercises",
    "K": "Knowledge & Skills",
    "P": "Personality & Behavior",
    "S": "Simulations",
}

_TOKEN_RE = re.compile(r"[a-z0-9\+\#\.]+")

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "with",
    "is", "are", "be", "this", "that", "test", "tests", "assessment",
    "assessments", "measuring", "measure", "measures", "candidate",
    "candidates", "multiple", "choice", "knowledge", "ability", "new",
    "skill", "skills", "role", "roles", "job", "level", "levels", "use",
    "used", "it", "its", "we", "you", "your", "i", "their", "as", "at",
    "by", "from", "into", "about", "also", "etc", "general",
}


def _tokenize(text: str) -> List[str]:
    text = text.lower().replace("c++", "cplusplus").replace("c#", "csharp")
    tokens = _TOKEN_RE.findall(text)
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


class Catalog:
    def __init__(self, path: str = DATA_PATH):
        with open(path, "r", encoding="utf-8") as f:
            self.items: List[Dict[str, Any]] = json.load(f)
        self._validate()
        self._build_index()

    def _validate(self):
        seen = set()

        for item in self.items:

            if "link" in item:
                item["url"] = item["link"]

            if "keys" in item:
                item["test_type"] = item["keys"]

            if "description" not in item:
                item["description"] = ""

            if "job_levels" not in item:
                item["job_levels"] = []

            if "languages" not in item:
                item["languages"] = []

            if "duration" not in item:
                item["duration"] = ""

            if "remote" not in item:
                item["remote"] = "unknown"

            if "adaptive" not in item:
                item["adaptive"] = "unknown"

            if "url" not in item:
                    continue

            assert item["url"].startswith("https://www.shl.com/")

            if item["name"] in seen:
                continue

            seen.add(item["name"])

    def _doc_text(self, item):
        return " ".join([
            item.get("name", ""),
            item.get("name", ""),
            item.get("description", ""),
            " ".join(item.get("job_levels", [])),
            " ".join(item.get("languages", [])),
            " ".join(item.get("test_type", [])),
            item.get("duration", ""),
            item.get("remote", ""),
            item.get("adaptive", ""),
        ])

    def _build_index(self):
        self.corpus_tokens = [_tokenize(self._doc_text(item)) for item in self.items]
        n_docs = len(self.corpus_tokens)

        df = Counter()
        for tokens in self.corpus_tokens:
            for term in set(tokens):
                df[term] += 1

        self.vocab = {term: i for i, term in enumerate(df.keys())}
        self.idf = np.zeros(len(self.vocab))
        for term, idx in self.vocab.items():
            self.idf[idx] = math.log((1 + n_docs) / (1 + df[term])) + 1.0

        self.doc_matrix = np.zeros((n_docs, len(self.vocab)))
        for i, tokens in enumerate(self.corpus_tokens):
            tf = Counter(tokens)
            for term, count in tf.items():
                if term in self.vocab:
                    self.doc_matrix[i, self.vocab[term]] = count * self.idf[self.vocab[term]]

        norms = np.linalg.norm(self.doc_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.doc_matrix_normed = self.doc_matrix / norms
        # Build semantic index
        texts = [self._doc_text(item) for item in self.items]
        build_semantic(self.items, texts)

    def _vectorize_query(self, text: str) -> np.ndarray:
        tokens = _tokenize(text)
        vec = np.zeros(len(self.vocab))
        tf = Counter(tokens)
        for term, count in tf.items():
            if term in self.vocab:
                vec[self.vocab[term]] = count * self.idf[self.vocab[term]]
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def search(
        self,
        query: str,
        top_k: int = 8,
        boost_types: Optional[List[str]] = None,
        max_duration: Optional[int] = None,
    ) -> List[Dict[str, Any]]:

        if not query.strip():
            return []

        qvec = self._vectorize_query(query)
        sims = self.doc_matrix_normed @ qvec

        scored = []

        for idx, item in enumerate(self.items):

            score = float(sims[idx])
            name = item.get("name", "").lower()
            desc = item.get("description", "").lower()
            query_lower = query.lower()

# Token boosts
            for token in _tokenize(query_lower):
                if token in name:
                    score += 0.40      # strong boost for title match
                elif token in desc:
                    score += 0.15

# Backend developer boost
            if "backend" in query_lower:
                if "java" in os.name or "spring" in os.name:
                    score += 0.35

# Java-specific boost
            if "java" in query_lower:
                if "java" in os.name:
                    score += 0.50

# Python-specific boost
            if "python" in query_lower:
                if "python" in os.name:
                    score += 0.50

# React-specific boost
            if "react" in query_lower:
                if "react" in os.name:
                    score += 0.50

# SQL-specific boost
            if "sql" in query_lower:
                if "sql" in os.name:
                    score += 0.35

            if boost_types:
                if any(t in item.get("test_type", []) for t in boost_types):
                    score *= 1.5

            if max_duration:
                duration = item.get("duration", "")
                m = re.search(r"(\d+)", duration)

                if m:
                    minutes = int(m.group(1))
                    if minutes > max_duration:
                        score *= 0.4

        # ⭐ THIS LINE WAS MISSING
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            item    
            for score, item in scored
            if score > 0
        ][:top_k]

    def find_by_name(self, name_fragment: str) -> Optional[Dict[str, Any]]:
        name_fragment = name_fragment.strip().lower()
        if not name_fragment:
            return None
        for item in self.items:
            if name_fragment == item["name"].lower():
                return item
        for item in self.items:
            if name_fragment in item["name"].lower() or item["name"].lower() in name_fragment:
                return item
        aliases = {
            "opq": "Occupational Personality Questionnaire (OPQ32r)",
            "opq32r": "Occupational Personality Questionnaire (OPQ32r)",
            "gsa": "Global Skills Assessment (GSA)",
            "mq": "Motivation Questionnaire (MQ)",
            "sjt": "Situational Judgement Test (SJT) - General",
            "wpi": "Workplace Personality Inventory (WPI)",
            "rwq": "Remote Work Questionnaire (RWQ)",
        }
        key = re.sub(r"[^a-z0-9]", "", name_fragment)
        if key in aliases:
            target = aliases[key]
            for item in self.items:
                if item["name"] == target:
                    return item
        import difflib
        names = [item["name"] for item in self.items]
        matches = difflib.get_close_matches(name_fragment, [n.lower() for n in names], n=1, cutoff=0.6)
        if matches:
            for item in self.items:
                if item["name"].lower() == matches[0]:
                    return item
        return None


_catalog_singleton: Optional[Catalog] = None


def get_catalog() -> Catalog:
    global _catalog_singleton
    if _catalog_singleton is None:
        _catalog_singleton = Catalog()
    return _catalog_singleton
