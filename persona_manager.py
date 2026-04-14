import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import chromadb
from sentence_transformers import SentenceTransformer

import env_setup

import config


class PersonaManager:
    def __init__(
        self,
        persona_file: str = None,
        db_dir: str = None,
        min_rating: int = None,
        top_k: int = None,
        decay_factor: float = None,
        reset_hours: int = None,
        max_penalty: float = None,
    ):
        self.persona_file = Path(persona_file or config.PERSONA_FILE)
        self.db_dir = Path(db_dir or config.PERSONA_DB_DIR)
        self.min_rating = min_rating or config.PERSONA_MIN_RATING
        self.top_k = top_k or config.PERSONA_TOP_K
        self.decay_factor = decay_factor or config.REPETITION_DECAY
        self.reset_hours = reset_hours or config.REPETITION_RESET_HOURS
        self.max_penalty = max_penalty or config.REPETITION_MAX_PENALTY

        self.embedding_model = None
        self.collection = None
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.persona_file.parent.mkdir(parents=True, exist_ok=True)

    def load_embedding_model(self):
        if self.embedding_model is None:
            self.embedding_model = SentenceTransformer(
                config.EMBEDDING_MODEL, device="cuda"
            )
        return self.embedding_model

    def load_persona_db(self):
        if self.collection is None:
            self.load_embedding_model()
            client = chromadb.PersistentClient(path=str(self.db_dir))
            self.collection = client.get_or_create_collection(
                name="user_persona",
                metadata={"hnsw:space": "cosine"}
            )
        return self.collection

    def save_dialogue(
        self,
        user_input: str,
        assistant_response: str,
        rating: int = None,
        reason: str = None,
    ) -> str:
        record_id = str(uuid.uuid4())
        record = {
            "id": record_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dialogue": {
                "user_input": user_input,
                "assistant_response": assistant_response,
            },
            "feedback": {
                "rating": rating,
                "reason": reason,
            },
            "embedding_id": None,
            "usage_count": 0,
            "last_used": None,
        }

        with open(self.persona_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        if self._should_add_to_rag(rating):
            embedding_id = self._add_to_rag(record)
            record["embedding_id"] = embedding_id
            self._update_record_embedding_id(record_id, embedding_id)

        return record_id

    def _should_add_to_rag(self, rating: int) -> bool:
        return rating is not None and rating >= 4

    def _add_to_rag(self, record: dict) -> str:
        self.load_persona_db()
        embedding_id = f"emb_{record['id']}"

        rating = record["feedback"]["rating"] or 0
        reason = record["feedback"].get("reason") or ""

        doc_text = f"用户问: {record['dialogue']['user_input']}\n助手答: {record['dialogue']['assistant_response']}"
        embedding = self.embedding_model.encode([doc_text])

        self.collection.add(
            ids=[embedding_id],
            embeddings=embedding.tolist(),
            documents=[doc_text],
            metadatas=[{
                "record_id": record["id"],
                "rating": rating,
                "reason": reason,
                "usage_count": 0,
                "timestamp": record["timestamp"],
            }]
        )

        return embedding_id

    def add_knowledge_entry(self, content: str, metadata: dict = None) -> str:
        self.load_persona_db()
        entry_id = f"kb_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        embedding = self.embedding_model.encode([content])
        
        entry_metadata = {
            "record_id": entry_id,
            "rating": metadata.get("rating", 5) if metadata else 5,
            "reason": metadata.get("reason", "") if metadata else "",
            "usage_count": 0,
            "timestamp": timestamp,
            "source": metadata.get("source", "manual") if metadata else "manual",
        }
        
        if metadata:
            for key in ["feedback_id", "feedback_type", "user_input"]:
                if key in metadata:
                    entry_metadata[key] = metadata[key]
        
        self.collection.add(
            ids=[entry_id],
            embeddings=embedding.tolist(),
            documents=[content],
            metadatas=[entry_metadata]
        )
        
        return entry_id

    def _update_record_embedding_id(self, record_id: str, embedding_id: str):
        if not self.persona_file.exists():
            return

        lines = []
        with open(self.persona_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record["id"] == record_id:
                    record["embedding_id"] = embedding_id
                lines.append(json.dumps(record, ensure_ascii=False))

        with open(self.persona_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def update_feedback(
        self,
        record_id: str,
        rating: int = None,
        reason: str = None,
    ) -> bool:
        if not self.persona_file.exists():
            return False

        lines = []
        updated = False
        with open(self.persona_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record["id"] == record_id:
                    if rating is not None:
                        record["feedback"]["rating"] = rating
                    if reason is not None:
                        record["feedback"]["reason"] = reason
                    updated = True

                    if self._should_add_to_rag(record["feedback"]["rating"]):
                        if not record.get("embedding_id"):
                            embedding_id = self._add_to_rag(record)
                            record["embedding_id"] = embedding_id

                lines.append(json.dumps(record, ensure_ascii=False))

        if updated:
            with open(self.persona_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

        return updated

    def retrieve_persona_context(self, query: str) -> Tuple[List[dict], List[dict]]:
        if self.collection is None:
            return [], []

        query_embedding = self.embedding_model.encode([query])
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=self.top_k * 2,
            include=["documents", "metadatas", "distances"]
        )

        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        penalized_results = self._apply_repetition_penalty(
            list(zip(documents, metadatas, distances))
        )

        positive_items = []
        negative_items = []
        for doc, meta, score in penalized_results:
            rating = meta.get("rating", 0)
            item = {
                "document": doc,
                "rating": rating,
                "reason": meta.get("reason", ""),
            }
            if rating >= self.min_rating:
                positive_items.append(item)
                self._increment_usage_count(meta.get("record_id"))
            else:
                negative_items.append(item)
                self._increment_usage_count(meta.get("record_id"))

        return positive_items[:self.top_k], negative_items[:self.top_k]

    def _apply_repetition_penalty(
        self, results: List[Tuple[str, dict, float]]
    ) -> List[Tuple[str, dict, float]]:
        penalized = []
        now = datetime.now()

        for doc, meta, distance in results:
            usage_count = meta.get("usage_count", 0)
            timestamp_str = meta.get("last_used") or meta.get("timestamp")

            last_used = None
            if timestamp_str:
                try:
                    last_used = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except:
                    pass

            penalty = 1.0
            if last_used and (now - last_used) < timedelta(hours=self.reset_hours):
                penalty = max(
                    self.max_penalty,
                    1 - usage_count * self.decay_factor
                )

            adjusted_score = distance * penalty
            penalized.append((doc, meta, adjusted_score))

        return sorted(penalized, key=lambda x: x[2], reverse=True)

    def _increment_usage_count(self, record_id: str):
        if not record_id or not self.persona_file.exists():
            return

        lines = []
        with open(self.persona_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record["id"] == record_id:
                    record["usage_count"] = record.get("usage_count", 0) + 1
                    record["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if record.get("embedding_id"):
                        self._update_embedding_metadata(
                            record["embedding_id"],
                            record["usage_count"],
                            record["last_used"]
                        )

                lines.append(json.dumps(record, ensure_ascii=False))

        with open(self.persona_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _update_embedding_metadata(self, embedding_id: str, usage_count: int, last_used: str):
        if self.collection is None:
            return

        try:
            self.collection.update(
                ids=[embedding_id],
                metadatas=[{
                    "usage_count": usage_count,
                    "last_used": last_used,
                }]
            )
        except:
            pass

    def get_recent_dialogues(self, limit: int = 10) -> List[dict]:
        if not self.persona_file.exists():
            return []

        dialogues = []
        with open(self.persona_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                dialogues.append(json.loads(line))

        return dialogues[-limit:]

    def get_last_dialogue_id(self) -> Optional[str]:
        dialogues = self.get_recent_dialogues(limit=1)
        if dialogues:
            return dialogues[0]["id"]
        return None

    def clear_all(self):
        if self.persona_file.exists():
            self.persona_file.unlink()

        if self.collection is not None:
            client = chromadb.PersistentClient(path=str(self.db_dir))
            try:
                client.delete_collection("user_persona")
            except:
                pass
            self.collection = None


_persona_manager_instance: Optional[PersonaManager] = None


def get_persona_manager() -> PersonaManager:
    global _persona_manager_instance
    if _persona_manager_instance is None:
        _persona_manager_instance = PersonaManager()
    return _persona_manager_instance
