"""
app/exam/idf_cache.py

Subject-level IDF cache.

Persists per-subject word-document-count dictionaries as pickle files so that
IDF stabilises across the full subject corpus rather than being recomputed from
only the current module's documents.

Thread / process safety: uses an adjacent .lock file with a spin-wait
(os.O_CREAT | O_EXCL — atomic on both POSIX and Windows NTFS) so concurrent
Celery workers do not corrupt the pickle.
"""
import math
import os
import pickle
import tempfile
import time

from app.utils.logger import get_logger

logger = get_logger(__name__)

_LOCK_TIMEOUT = 10    # seconds to wait for lock before giving up
_LOCK_POLL    = 0.2   # poll interval in seconds


# ---------------------------------------------------------------------------
# Cross-platform advisory file lock (no external dependency)
# ---------------------------------------------------------------------------

def _acquire_lock(lock_path: str) -> bool:
    """
    Spin-wait until we can create an exclusive .lock file.
    Returns True when the lock is held, False on timeout.
    """
    deadline = time.monotonic() + _LOCK_TIMEOUT
    while time.monotonic() < deadline:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(_LOCK_POLL)
    return False


def _release_lock(lock_path: str) -> None:
    try:
        os.remove(lock_path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Main cache class
# ---------------------------------------------------------------------------

class SubjectIDFCache:
    """
    Manages per-subject TF-IDF corpus counts on disk.

    Cache file layout:
        {cache_dir}/{subject_id}.idf.pkl
            → pickle of {'word_doc_counts': {word: int}, 'total_doc_count': int}

    Usage (in saved_module.py, after tfidf_engine.process_documents()):
        SubjectIDFCache().merge_and_apply(module.subject_id, tfidf_engine)
    """

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = cache_dir or os.getenv(
            "AI_IDF_CACHE_DIR",
            os.path.join("uploads", "idf_cache")
        )
        os.makedirs(self.cache_dir, exist_ok=True)

    # ------------------------------------------------------------------
    def _cache_path(self, subject_id: int) -> str:
        return os.path.join(self.cache_dir, f"{subject_id}.idf.pkl")

    def _lock_path(self, subject_id: int) -> str:
        return os.path.join(self.cache_dir, f"{subject_id}.idf.lock")

    # ------------------------------------------------------------------
    def load(self, subject_id: int) -> dict:
        """
        Load cached IDF data for *subject_id*.
        Returns {'word_doc_counts': dict, 'total_doc_count': int}
        or an empty dict if no cache file exists yet.
        """
        path = self._cache_path(subject_id)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception as exc:
            logger.warning(f"IDF cache load failed for subject {subject_id}: {exc}")
            return {}

    def save(self, subject_id: int, word_doc_counts: dict, total_doc_count: int) -> None:
        """
        Atomically save IDF data for *subject_id*.
        Uses temp-file + os.replace() so partial writes are never visible.
        """
        lock = self._lock_path(subject_id)
        if not _acquire_lock(lock):
            logger.warning(f"IDF cache lock timeout for subject {subject_id}; skipping save")
            return
        try:
            data = {
                "word_doc_counts": word_doc_counts,
                "total_doc_count": total_doc_count,
            }
            fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir)
            try:
                with os.fdopen(fd, "wb") as f:
                    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
                os.replace(tmp_path, self._cache_path(subject_id))
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as exc:
            logger.error(f"IDF cache save failed for subject {subject_id}: {exc}")
        finally:
            _release_lock(lock)

    # ------------------------------------------------------------------
    def merge_and_apply(self, subject_id: int, tfidf_engine) -> None:
        """
        1. Load existing subject-level IDF data from disk.
        2. Merge with tfidf_engine's current per-module document counts.
        3. Recompute tfidf_engine.idf from the merged counts.
        4. Persist updated counts back to disk.

        *tfidf_engine* must have already called process_documents() so that
        tfidf_engine.documents and tfidf_engine.vocab are populated.
        """
        cached       = self.load(subject_id)
        merged       = dict(cached.get("word_doc_counts", {}))
        merged_total = int(cached.get("total_doc_count", 0))

        # Merge current module's word-doc counts into subject-level counts
        current_wdc   = tfidf_engine.get_word_doc_counts()
        current_total = len(tfidf_engine.documents)

        for word, count in current_wdc.items():
            merged[word] = merged.get(word, 0) + count
        merged_total += current_total

        # Push merged IDF back into the engine
        tfidf_engine.apply_merged_idf(merged, merged_total)

        # Persist updated counts
        self.save(subject_id, merged, merged_total)

        logger.info(
            f"IDF cache merged for subject {subject_id}: "
            f"{len(merged)} vocab terms, {merged_total} total docs "
            f"(+{current_total} this module)"
        )
