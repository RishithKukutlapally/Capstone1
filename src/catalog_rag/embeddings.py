from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

from .logging_utils import get_logger

logger = get_logger("catalog_rag.embeddings")

_cache = {}

class LocalEmbeddings(Embeddings):
    def __init__(self, cfg):
        self.cfg = cfg
        if cfg.model_name not in _cache:
            logger.info("Loading embedding model %s", cfg.model_name)
            _cache[cfg.model_name] = SentenceTransformer(cfg.model_name, device=cfg.device)

        # not self.model: ragas reads .model expecting a model-name string
        self.encoder = _cache[cfg.model_name]
        self.model_name = cfg.model_name

    def _encode(self, texts):
        vectors = self.encoder.encode(
            texts,
            batch_size=self.cfg.batch_size,
            normalize_embeddings=self.cfg.normalize,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]

    def embed_documents(self, texts):
        return self._encode([self.cfg.document_instruction + t for t in texts])

    def embed_query(self, text):
        return self._encode([self.cfg.query_instruction + text])[0]
