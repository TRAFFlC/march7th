from typing import List, Tuple
from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self):
        self.model = CrossEncoder(
            self.model_name,
            max_length=512,
            device="cpu"
        )

    def rerank(self, query: str, documents: List[str], top_k: int = 3) -> List[Tuple[str, float]]:
        if not documents:
            return []

        if self.model is None:
            self._load_model()

        pairs = [[query, doc] for doc in documents]
        scores = self.model.predict(pairs)

        if isinstance(scores, list):
            scored_docs = list(zip(documents, scores))
        else:
            scored_docs = list(zip(documents, scores.tolist()))

        scored_docs.sort(key=lambda x: x[1], reverse=True)

        return scored_docs[:top_k]

    def reload(self, model_name: str = None):
        if model_name:
            self.model_name = model_name
        self.model = None
        self._load_model()
