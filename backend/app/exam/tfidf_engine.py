import math
import os
import re
from collections import Counter
import numpy as np
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.stem import WordNetLemmatizer
from nltk import pos_tag
from nltk.corpus import wordnet as _wn_corpus
from app.utils.logger import get_logger

try:
    import spacy
except Exception:
    spacy = None

# Module-level NLTK lemmatizer (shared across instances for efficiency)
_wnl = WordNetLemmatizer()


def _wn_pos(treebank_tag):
    """Map Penn Treebank POS tag to WordNet POS constant."""
    if treebank_tag.startswith('J'):
        return _wn_corpus.ADJ
    elif treebank_tag.startswith('V'):
        return _wn_corpus.VERB
    elif treebank_tag.startswith('R'):
        return _wn_corpus.ADV
    return _wn_corpus.NOUN

logger = get_logger(__name__)

# ---- Configurable quality thresholds (env overrides) -------------------------
MIN_TFIDF_SCORE = float(os.getenv("AI_MIN_TFIDF_SCORE", "0.02"))
MIN_KEYWORD_QUALITY = float(os.getenv("AI_MIN_KEYWORD_QUALITY", "0.20"))
MIN_ENTROPY = float(os.getenv("AI_MIN_KEYWORD_ENTROPY", "1.2"))
MAX_KEYWORDS = int(os.getenv("AI_MAX_KEYWORDS", "80"))
MAX_KEYWORDS_PER_CHUNK = int(os.getenv("AI_MAX_KEYWORDS_PER_CHUNK", "25"))
FORCE_TOPK_WHEN_EMPTY = os.getenv("AI_TFIDF_FORCE_TOPK", "1") == "1"
DOMAIN_STOPWORDS = {
    'value', 'values', 'mean', 'means', 'purpose', 'function', 'define', 'definition',
    'concept', 'describe', 'explain', 'identified', 'identify', 'screen', 'metro',
    'region', 'paired', 'test', 'sample', 'true', 'false', 'question', 'answer',
    'supported', 'therefore', 'network', 'networks', 'communication', 'computer',
    'computer network', 'class network', 'speed', 'provides', 'enables', 'device', 'devices',
    'network interface', 'computer networking', 'networking', 'nic', 'interface', 'interfaces',
    'router', 'routers', 'hop', 'hops', 'segment', 'segments', 'subnet', 'subnetting',
    'address', 'addresses', 'ip address', 'mac address', 'broadcast', 'reserved',
    'module', 'section', 'chapter', 'complete the sentence',
    'update', 'updates', 'timer', 'seconds'
}

# STRICT: Forbidden words that should not appear in generated questions
FORBIDDEN_WORDS = {'one', 'that', 'this', 'to', 'you', 'of'}


class TFIDFEngine:
    """
    IMPROVED: Enhanced TF-IDF engine with:
    - Better keyword filtering
    - Improved scoring algorithm
    - Context-aware term extraction
    - Quality metrics for extracted terms
    """
    
    def __init__(self, min_word_length=3, max_word_length=50):
        self.documents = []
        self.vocab = set()
        self.idf = {}
        self.min_word_length = min_word_length
        self.max_word_length = max_word_length
        self._spacy_nlp = None  # lazy-loaded

        # IMPROVED: Expanded stopwords list
        self.stopwords = {
            # Articles & Determiners
            'the', 'a', 'an', 'this', 'that', 'these', 'those',
            
            # Prepositions
            'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about',
            'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between',
            'under', 'over', 'out', 'off', 'down', 'upon', 'against', 'among', 'across',
            
            # Conjunctions
            'and', 'or', 'but', 'nor', 'yet', 'so', 'as', 'if', 'than', 'though',
            'although', 'unless', 'because', 'since', 'while', 'whereas',
            
            # Pronouns
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'its', 'our', 'their', 'mine', 'yours', 'ours', 'theirs',
            'myself', 'yourself', 'himself', 'herself', 'itself', 'ourselves', 'themselves',
            'who', 'whom', 'whose', 'which', 'what',
            
            # Auxiliary & Modal verbs
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am',
            'have', 'has', 'had', 'having',
            'do', 'does', 'did', 'doing', 'done',
            'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'shall',
            
            # Common verbs
            'get', 'got', 'getting', 'make', 'made', 'making', 'go', 'going', 'went', 'gone',
            'come', 'coming', 'came', 'take', 'taking', 'took', 'taken', 'see', 'seeing', 'saw', 'seen',
            
            # Adverbs & Modifiers
            'not', 'no', 'yes', 'very', 'too', 'quite', 'rather', 'just', 'only', 'even',
            'also', 'still', 'already', 'yet', 'again', 'more', 'most', 'much', 'many',
            'some', 'any', 'all', 'each', 'every', 'both', 'few', 'several', 'other',
            
            # Question words
            'when', 'where', 'why', 'how',
            
            # Others
            'here', 'there', 'then', 'now', 'today', 'tomorrow', 'yesterday',
            'always', 'never', 'sometimes', 'often', 'usually', 'rarely',
            'such', 'same', 'own', 'different', 'new', 'old', 'good', 'bad',
            
            # Include forbidden words
            'one', 'two', 'three'
        }
        
        # IMPROVED: Technical term patterns to preserve
        self.technical_patterns = [
            r'^[A-Z]{2,}$',  # Acronyms (CPU, RAM, API)
            r'^[a-z]+[A-Z][a-z]+',  # camelCase
            r'^[A-Z][a-z]+[A-Z]',  # PascalCase
            r'^\w+\-\w+$',  # hyphenated-terms
            r'^\w+_\w+$',  # snake_case
        ]

    def _get_spacy(self):
        """Lazy load spaCy (small) for POS filtering; return None if unavailable."""
        if self._spacy_nlp is not None:
            return self._spacy_nlp
        if spacy is None:
            self._spacy_nlp = None
            return None
        try:
            model = os.getenv("AI_SPACY_MODEL", "en_core_web_sm")
            self._spacy_nlp = spacy.load(model)
        except Exception:
            try:
                self._spacy_nlp = spacy.load("en_core_web_sm")
            except Exception:
                self._spacy_nlp = None
        return self._spacy_nlp

    def _pos_ok(self, word: str) -> bool:
        """Allow only nouns/adjectives using NLTK POS tagger (lighter than spaCy)."""
        if not word:
            return True
        try:
            tag = pos_tag([word])[0][1]
            # NN* = nouns, NNP* = proper nouns, JJ* = adjectives
            return tag.startswith(('NN', 'JJ'))
        except Exception:
            return True

    def _is_technical_term(self, word):
        """Check if word matches technical term patterns."""
        for pattern in self.technical_patterns:
            if re.match(pattern, word):
                return True
        return False
    
    def _clean_word(self, word):
        """
        IMPROVED: Clean and validate a word with better filtering.
        """
        # Preserve technical terms before cleaning
        if self._is_technical_term(word):
            if self.min_word_length <= len(word) <= self.max_word_length:
                return word.lower()
        
        # Remove non-alphanumeric characters from edges
        word = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', word)
        
        # Check length constraints
        if len(word) < self.min_word_length or len(word) > self.max_word_length:
            return None
        
        # Filter stopwords and forbidden words
        word_lower = word.lower()
        if word_lower in self.stopwords or word_lower in FORBIDDEN_WORDS:
            return None
        
        # IMPROVED: Filter pure numbers
        if word.isdigit():
            return None
        
        # IMPROVED: Filter words with too many numbers
        digit_count = sum(c.isdigit() for c in word)
        if digit_count > len(word) / 2:  # More than 50% digits
            return None
        
        return word_lower
    
    def _tokenize_and_lemmatize(self, text):
        """Tokenize with NLTK word_tokenize, clean, and lemmatize each token.

        Lemmatization unifies inflected forms (e.g. "networks"/"network",
        "computing"/"compute") so they are counted as the same term.
        """
        try:
            tokens = word_tokenize(text)
        except Exception:
            tokens = text.split()
        cleaned = []
        for tok in tokens:
            w = self._clean_word(tok)
            if w:
                try:
                    tag = pos_tag([w])[0][1]
                    w = _wnl.lemmatize(w, _wn_pos(tag))
                except Exception:
                    pass
                cleaned.append(w)
        return cleaned

    def add_document(self, document):
        """Add a document to the corpus."""
        if not document or not isinstance(document, str):
            return

        self.documents.append(document)
        words = self._tokenize_and_lemmatize(document)
        self.vocab.update(words)

    def compute_tf(self, document):
        """
        IMPROVED: Compute term frequency with position weighting.
        """
        words = self._tokenize_and_lemmatize(document)
        
        if not words:
            return {}
        
        word_count = len(words)
        tf = Counter(words)
        
        # IMPROVED: Add position weighting (early terms slightly more important)
        position_weighted_tf = {}
        for word, count in tf.items():
            # Find first occurrence position
            try:
                first_position = words.index(word)
                # Position weight: 1.0 for first 10%, decreasing to 0.9
                position_weight = 1.0 - (first_position / word_count) * 0.1
                position_weighted_tf[word] = (count / word_count) * position_weight
            except ValueError:
                position_weighted_tf[word] = count / word_count
        
        return position_weighted_tf
    
    def _doc_word_sets(self):
        """Pre-compute the set of cleaned+lemmatized words for each corpus document."""
        if not hasattr(self, '_cached_doc_sets') or len(self._cached_doc_sets) != len(self.documents):
            self._cached_doc_sets = [
                set(self._tokenize_and_lemmatize(doc)) for doc in self.documents
            ]
        return self._cached_doc_sets

    def compute_idf(self):
        """
        IMPROVED: Compute inverse document frequency with smoothing.
        """
        if not self.documents:
            logger.warning("No documents in corpus for IDF computation")
            return

        total_docs = len(self.documents)
        doc_sets = self._doc_word_sets()

        for word in self.vocab:
            # Count documents containing this word
            doc_count = sum(1 for ds in doc_sets if word in ds)
            
            if doc_count > 0:
                # IMPROVED: Enhanced IDF formula with smoothing
                # Standard: log((N + 1) / (df + 1)) + 1
                # Enhanced: Add boost for rare but meaningful terms
                base_idf = math.log((total_docs + 1) / (doc_count + 1)) + 1
                
                # Boost technical terms
                if self._is_technical_term(word):
                    base_idf *= 1.2
                
                # Penalize very common terms (appear in >80% of docs)
                if doc_count > (total_docs * 0.8):
                    base_idf *= 0.8
                
                self.idf[word] = base_idf
            else:
                self.idf[word] = 0

    def get_word_doc_counts(self) -> dict:
        """
        Return {word: doc_count} for the current corpus.
        Must be called after process_documents().
        Used by SubjectIDFCache to persist cross-module IDF state.
        """
        counts = {}
        doc_sets = self._doc_word_sets()
        for word in self.vocab:
            cnt = sum(1 for ds in doc_sets if word in ds)
            if cnt > 0:
                counts[word] = cnt
        return counts

    def apply_merged_idf(self, merged_word_doc_counts: dict, merged_total: int) -> None:
        """
        Recompute self.idf using pre-merged cross-subject document counts.
        Uses the same enhanced formula as compute_idf() for consistency.
        Called by SubjectIDFCache.merge_and_apply() after merging counts.
        """
        if merged_total == 0:
            return
        self.idf = {}
        for word in self.vocab:
            dc = merged_word_doc_counts.get(word, 0)
            if dc > 0:
                base_idf = math.log((merged_total + 1) / (dc + 1)) + 1
                if self._is_technical_term(word):
                    base_idf *= 1.2
                if dc > merged_total * 0.8:
                    base_idf *= 0.8
                self.idf[word] = base_idf
            else:
                # Word seen only in this module — treat as rare (df=1 in merged corpus)
                self.idf[word] = math.log((merged_total + 1) / 2) + 1

    def compute_tfidf(self, document):
        """
        IMPROVED: Compute TF-IDF scores with enhanced weighting.
        """
        if not self.idf:
            logger.info("Computing IDF for corpus...")
            self.compute_idf()
        
        tf = self.compute_tf(document)
        tfidf = {}
        
        for word, tf_score in tf.items():
            if word in self.idf:
                tfidf[word] = tf_score * self.idf[word]
            else:
                # If word not in IDF, give it a default low score
                tfidf[word] = tf_score * 0.5
        
        return tfidf
    
    def extract_keywords(self, document, top_n=20):
        """
        IMPROVED: Extract top keywords with quality filtering.
        """
        if not document or not isinstance(document, str):
            logger.warning("Invalid document provided for keyword extraction")
            return []
        
        # If no corpus, add this document to build IDF
        if not self.documents:
            logger.info("No corpus available, building from current document")
            # Split document into sentences as mini-documents (Punkt tokenizer)
            sentences = sent_tokenize(document) if document.strip() else []
            for sentence in sentences:
                if sentence.strip():
                    self.add_document(sentence.strip())
            self.compute_idf()
        
        tfidf = self.compute_tfidf(document)

        if not tfidf:
            logger.warning("No TF-IDF scores computed")
            return []

        # ---- Diagnostics: see the score scale ---------------------------------
        scores_arr = np.array(list(tfidf.values()), dtype=float)
        if scores_arr.size:
            logger.info(
                "TF-IDF stats: min=%.6f max=%.6f p90=%.6f p95=%.6f p99=%.6f terms=%d",
                scores_arr.min(), scores_arr.max(),
                np.quantile(scores_arr, 0.90),
                np.quantile(scores_arr, 0.95),
                np.quantile(scores_arr, 0.99),
                scores_arr.size
            )

        # ---- Candidate selection: top-K or dynamic cutoff ---------------------
        cap = min(MAX_KEYWORDS_PER_CHUNK, top_n, MAX_KEYWORDS)
        precap = max(cap * 4, 50)  # grab a bigger pool before quality filtering

        # Sort by raw tfidf score
        sorted_terms = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)
        # Keep non-zero scores first
        candidates = [(w, s) for w, s in sorted_terms if s > 0][:precap]

        # Dynamic cutoff (top 15% by score) if we still have too many
        if len(candidates) > precap:
            score_vals = np.array([s for _, s in candidates], dtype=float)
            cutoff = np.quantile(score_vals, 0.85)
            candidates = [(w, s) for w, s in candidates if s >= cutoff][:precap]

        # If still empty, fall back to spaCy/regex later
        limited = []

        # ---- Quality filters applied to candidates ----------------------------
        _skipped_quality = 0
        for word, score in candidates:
            if len(word) < self.min_word_length or len(word) > self.max_word_length:
                continue
            if word.lower() in DOMAIN_STOPWORDS:
                continue
            if not self._pos_ok(word):
                continue
            if document.lower().count(word) < 1:
                continue
            digit_count = sum(c.isdigit() for c in word)
            if not self._is_technical_term(word) and digit_count > len(word) / 2:
                continue

            quality = self.analyze_keyword_quality(document, word, precomputed_tfidf=tfidf).get('quality_score', 0.0)
            if quality < MIN_KEYWORD_QUALITY:
                _skipped_quality += 1
                continue

            limited.append((word, score))
            if len(limited) >= cap:
                break

        logger.info(
            "TF-IDF filter: %d total words, %d candidates, %d failed quality>=%.3f, %d final keywords (cap=%d)",
            len(tfidf), len(candidates), _skipped_quality, MIN_KEYWORD_QUALITY, len(limited), cap
        )

        # If nothing survived thresholds, optionally keep top-K raw tfidf to avoid empty set
        if not limited and FORCE_TOPK_WHEN_EMPTY and tfidf:
            limited = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)[:cap]
            logger.warning(
                "TF-IDF empty after filters; using raw top-%d terms (FORCE_TOPK_WHEN_EMPTY enabled)",
                len(limited)
            )

        # Fallback when TF-IDF yields nothing: use spaCy noun/proper-noun frequency
        if not limited:
            nlp = self._get_spacy()
            if nlp:
                doc = nlp(document)
                noun_freq = Counter(
                    t.lemma_.lower()
                    for t in doc
                    if t.pos_ in {"NOUN", "PROPN"}
                    and 3 <= len(t.text) <= self.max_word_length
                    and t.lemma_.lower() not in self.stopwords
                    and t.lemma_.lower() not in DOMAIN_STOPWORDS
                    and t.lemma_.lower() not in FORBIDDEN_WORDS
                )
                if noun_freq:
                    fallback = noun_freq.most_common(cap)
                    limited = [(w, 1.0) for w, _ in fallback]
                    logger.warning(
                        "TF-IDF empty; using spaCy noun fallback with %d keywords (cap=%d)",
                        len(limited), cap
                    )
        # Final safety fallback: simple frequency over words (never return empty)
        if not limited:
            tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,50}", document)
            freq = Counter(
                t.lower()
                for t in tokens
                if t.lower() not in self.stopwords
                and t.lower() not in DOMAIN_STOPWORDS
                and t.lower() not in FORBIDDEN_WORDS
                and len(t) <= self.max_word_length
            )
            if freq:
                fallback = freq.most_common(cap)
                limited = [(w, 1.0) for w, _ in fallback]
                logger.warning(
                    "TF-IDF empty; using regex frequency fallback with %d keywords (cap=%d)",
                    len(limited), cap
                )

        return limited
    
    def process_documents(self, documents):
        """
        IMPROVED: Process multiple documents with better corpus building.
        """
        if not documents:
            logger.warning("No documents provided for processing")
            return
        
        self.documents = []
        self.vocab = set()
        
        valid_doc_count = 0
        for doc in documents:
            if doc and isinstance(doc, str) and len(doc.strip()) > 0:
                self.add_document(doc)
                valid_doc_count += 1
        
        logger.info(f"Processed {valid_doc_count} valid documents with vocabulary size: {len(self.vocab)}")
        
        if valid_doc_count > 0:
            self.compute_idf()
    
    def get_keywords_from_multiple_docs(self, documents, top_n=20):
        """
        IMPROVED: Extract keywords from multiple documents with aggregation.
        """
        if not documents:
            logger.warning("No documents provided for keyword extraction")
            return []
        
        self.process_documents(documents)
        
        # Aggregate TF-IDF scores across all documents
        aggregated_tfidf = {}
        
        for doc in documents:
            if not doc or not isinstance(doc, str):
                continue
                
            tfidf = self.compute_tfidf(doc)
            for word, score in tfidf.items():
                if word in aggregated_tfidf:
                    aggregated_tfidf[word] += score
                else:
                    aggregated_tfidf[word] = score
        
        if not aggregated_tfidf:
            logger.warning("No aggregated TF-IDF scores computed")
            return []
        
        # IMPROVED: Normalize by document count
        doc_count = len([d for d in documents if d and isinstance(d, str)])
        for word in aggregated_tfidf:
            aggregated_tfidf[word] /= doc_count
        
        # IMPROVED: Apply quality filters
        filtered_tfidf = {}
        for word, score in aggregated_tfidf.items():
            # Quality checks
            if len(word) < self.min_word_length:
                continue
            
            # Check word appears in multiple documents
            doc_frequency = sum(
                1 for doc in documents 
                if doc and isinstance(doc, str) and word in doc.lower()
            )
            
            if doc_frequency < 2:  # Must appear in at least 2 documents
                continue
            
            filtered_tfidf[word] = score
        
        # Sort by aggregated TF-IDF score
        sorted_keywords = sorted(filtered_tfidf.items(), key=lambda x: x[1], reverse=True)
        
        logger.info(f"Extracted {len(sorted_keywords)} aggregated keywords, returning top {top_n}")
        
        # Return top N keywords
        return sorted_keywords[:top_n]
    
    def get_keyword_context(self, document, keyword, context_size=200):
        """
        IMPROVED: Extract context around keyword occurrences.
        """
        contexts = []
        
        # Find all occurrences
        pattern = r'\b' + re.escape(keyword) + r'\b'
        matches = re.finditer(pattern, document, re.IGNORECASE)
        
        for match in matches:
            start = max(0, match.start() - context_size // 2)
            end = min(len(document), match.end() + context_size // 2)
            
            context = document[start:end]
            contexts.append(context)
        
        return contexts
    
    def analyze_keyword_quality(self, document, keyword, precomputed_tfidf=None):
        """
        NEW: Analyze the quality of a keyword in a document.
        Returns a quality score (0-1) and metrics.
        """
        metrics = {
            'frequency': 0,
            'spread': 0.0,
            'context_diversity': 0,
            'tfidf_score': 0.0,
            'quality_score': 0.0
        }
        
        # Frequency
        frequency = document.lower().count(keyword.lower())
        metrics['frequency'] = frequency
        
        if frequency == 0:
            return metrics
        
        # Spread
        positions = [m.start() for m in re.finditer(r'\b' + re.escape(keyword) + r'\b', document.lower())]
        if len(positions) >= 2:
            metrics['spread'] = (positions[-1] - positions[0]) / len(document)
        
        # Context diversity (unique contexts)
        contexts = self.get_keyword_context(document, keyword, 100)
        unique_contexts = len(set(contexts))
        metrics['context_diversity'] = unique_contexts
        
        # TF-IDF score
        if precomputed_tfidf is not None:
            metrics['tfidf_score'] = precomputed_tfidf.get(keyword.lower(), 0.0)
        else:
            _tfidf = self.compute_tfidf(document)
            metrics['tfidf_score'] = _tfidf.get(keyword.lower(), 0.0)
        
        # Calculate quality score
        # Weighted combination of metrics
        quality_score = (
            min(frequency / 10, 1.0) * 0.3 +  # Frequency (capped at 10)
            metrics['spread'] * 0.3 +  # Spread
            min(unique_contexts / 5, 1.0) * 0.2 +  # Context diversity (capped at 5)
            min(metrics['tfidf_score'], 1.0) * 0.2  # TF-IDF
        )
        
        metrics['quality_score'] = quality_score
        
        return metrics
