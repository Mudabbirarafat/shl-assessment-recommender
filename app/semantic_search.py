from sentence_transformers import SentenceTransformer
import numpy as np
import faiss

_model = SentenceTransformer("all-MiniLM-L6-v2")

_index = None
_embeddings = None
_items = None


def build(items, texts):
    global _index, _embeddings, _items

    _items = items

    _embeddings = _model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    dim = _embeddings.shape[1]

    _index = faiss.IndexFlatIP(dim)
    _index.add(_embeddings)


def search(query, top_k=10):

    if _index is None:
        return []

    q = _model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    scores, ids = _index.search(q, top_k)

    results = []

    for score, idx in zip(scores[0], ids[0]):
        if idx >= 0:
            results.append((float(score), _items[idx]))

    return results