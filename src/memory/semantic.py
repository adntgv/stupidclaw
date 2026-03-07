"""
Semantic Memory — Long-term fact storage with vector search (ChromaDB)
Uses lazy initialization to avoid blocking on ONNX model download.
"""
import logging
import threading
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SemanticMemory:
    """Stores facts, preferences, and important information with vector search"""
    
    def __init__(self, persist_dir: str = "/app/data/chromadb"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self._client = None
        self._init_lock = threading.Lock()
        self._ready = False
        self.collections: Dict[str, object] = {}
        
        # Start initialization in background thread
        self._init_thread = threading.Thread(target=self._lazy_init, daemon=True)
        self._init_thread.start()
    
    def _lazy_init(self):
        """Initialize ChromaDB client (downloads embedding model on first use)"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            with self._init_lock:
                self._client = chromadb.Client(Settings(
                    persist_directory=str(self.persist_dir),
                    anonymized_telemetry=False
                ))
                self._ready = True
                logger.info("ChromaDB initialized successfully")
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {e}")
    
    def _get_collection(self, chat_id: str):
        """Get or create collection for a user"""
        if not self._ready or self._client is None:
            return None
        
        if chat_id not in self.collections:
            collection_name = f"user_{chat_id}".replace("-", "_")[:63]
            self.collections[chat_id] = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"user_id": chat_id}
            )
        return self.collections[chat_id]
    
    def store(self, chat_id: str, text: str, metadata: Optional[Dict] = None):
        """Store a fact/preference with metadata (non-blocking if not ready)"""
        try:
            collection = self._get_collection(chat_id)
            if collection is None:
                logger.warning("ChromaDB not ready yet, skipping store")
                return
            
            import hashlib
            import time
            doc_id = hashlib.md5(f"{time.time()}_{text}".encode()).hexdigest()[:16]
            
            collection.add(
                documents=[text],
                metadatas=[metadata or {}],
                ids=[doc_id]
            )
            logger.info(f"Stored fact for {chat_id}: {text[:50]}")
        except Exception as e:
            logger.error(f"Failed to store fact: {e}")
    
    def recall(self, chat_id: str, query: str, limit: int = 5) -> List[str]:
        """Retrieve relevant facts based on semantic similarity"""
        try:
            collection = self._get_collection(chat_id)
            if collection is None:
                return []
            
            count = collection.count()
            if count == 0:
                return []
            
            results = collection.query(
                query_texts=[query],
                n_results=min(limit, count)
            )
            
            if results and results['documents']:
                return results['documents'][0]
            return []
        except Exception as e:
            logger.error(f"Failed to recall: {e}")
            return []
    
    def get_all_facts(self, chat_id: str, limit: int = 100) -> List[str]:
        """Get all stored facts for a user"""
        try:
            collection = self._get_collection(chat_id)
            if collection is None:
                return []
            
            count = collection.count()
            if count == 0:
                return []
            
            results = collection.get(limit=min(limit, count))
            return results.get('documents', [])
        except Exception as e:
            logger.error(f"Failed to get facts: {e}")
            return []
