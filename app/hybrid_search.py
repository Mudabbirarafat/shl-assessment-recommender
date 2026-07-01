from .catalog import get_catalog
from .semantic_search import search as semantic_search


def hybrid_search(query, top_k=8):

    catalog = get_catalog()

    tfidf = catalog.search(query, top_k=30)

    semantic = [
        item
        for score, item in semantic_search(query, top_k=30)
    ]

    merged = []

    seen = set()

    for item in tfidf + semantic:
        if item["name"] not in seen:
            merged.append(item)
            seen.add(item["name"])

    return merged[:top_k]