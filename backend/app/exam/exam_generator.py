import os
import random
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from app.exam.tfidf_engine import TFIDFEngine
from app.exam.hybrid_nlp import HybridNLPEngine
from app.exam.bloom_classifier import BloomClassifier
from app.exam.tos_generator import TOSGenerator
from app.exam.randomizer import QuestionRandomizer
from app.utils.logger import get_logger

import numpy as np

# Compatibility shim: older sentence-transformers (2.x) expects `cached_download`
# which was removed in newer huggingface_hub versions. Provide a lightweight
# alias to keep imports working without changing global packages.
try:
    import huggingface_hub
    if not hasattr(huggingface_hub, "cached_download"):
        huggingface_hub.cached_download = huggingface_hub.hf_hub_download
except Exception:
    # If huggingface_hub is missing or behaves unexpectedly, continue;
    # sentence_transformers import will raise a clearer error.
    pass

# NLTK imports 
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk import pos_tag
from nltk.corpus import wordnet
from nltk.stem import WordNetLemmatizer

logger = get_logger(__name__)


class ExamGenerator:
    """
    IMPROVED Exam Generator - Pure Python
    
    IMPROVEMENTS:
    - FIXED: Clean identification questions (no lesson headers, no exposed answers)
    - Better fill-in-blank (targets important words)
    - True/False mix (intelligent negation)
    - Quality MCQ
    """
    
    def __init__(self):
        self.tfidf_engine = TFIDFEngine()
        self.nlp_engine = HybridNLPEngine()
        self.bloom_classifier = BloomClassifier()
        self.tos_generator = TOSGenerator()
        self.randomizer = QuestionRandomizer()

        # Question tracking
        self.generated_questions = set()
        self._pearson_generated  = False   # at most one Pearson question per exam
        self.used_answers = set()

        self.t5_generator = None

        # AI ENHANCEMENT: Advanced NLP components (lazy loading)
        self._spacy_nlp = None
        self._sentence_transformer = None
        self._qa_pipeline = None

        # Speed caches — reset each generate_exam() call
        self._keyword_cache = {}          # hash(text[:200]) → enhanced keyword list
        self._q_embed_texts = []          # accepted question texts in order
        self._q_embed_matrix = None       # np.ndarray (N, D) — grows as questions are accepted

        # Math mode state — set in generate_exam() Phase 2
        self._math_mode = False           # True when module is primarily mathematical
        self._math_sentences = []         # Cached equation-bearing sentences
        self._math_concepts = {}          # {theorems, equations, definitions, named_constants}

        # Module-level distribution state (optional)
        self._module_question_targets = {}
        self._module_question_usage = {}

        logger.info("=" * 80)
        logger.info("✅ ExamGenerator Initialized - CLEAN Questions v2.0 + AI Enhancement")
        logger.info("=" * 80)
    
    def _get_question_generator(self):
        """Return the T5 question generator (lazy-loaded)."""
        if self.t5_generator is None:
            logger.info("Initializing T5 generator...")
            from app.exam.t5_generator import T5QuestionGenerator
            self.t5_generator = T5QuestionGenerator(model_name=os.getenv("AI_T5_MODEL", "t5-small"))
        return self.t5_generator

    # ===== AI ENHANCEMENT: Advanced NLP Lazy Loaders =====

    def _get_spacy_nlp(self):
        """Lazy load spaCy NLP pipeline with advanced features"""
        if self._spacy_nlp is None:
            try:
                import spacy

                logger.info("🔧 Loading spaCy NLP pipeline...")
                # Try to load configured model (default: en_core_web_md)
                _spacy_model    = os.getenv("AI_SPACY_MODEL", "en_core_web_md")
                _spacy_fallback = os.getenv("AI_SPACY_FALLBACK_MODEL", "en_core_web_sm")
                try:
                    self._spacy_nlp = spacy.load(_spacy_model)
                    logger.info(f"✅ Loaded {_spacy_model} (primary model)")
                except OSError:
                    # Fallback to smaller model
                    try:
                        self._spacy_nlp = spacy.load(_spacy_fallback)
                        logger.info(f"✅ Loaded {_spacy_fallback} (fallback model)")
                    except OSError:
                        logger.warning(f"⚠️ spaCy model not found, downloading {_spacy_fallback}...")
                        import spacy.cli as spacy_cli
                        spacy.cli.download(_spacy_fallback)
                        self._spacy_nlp = spacy.load(_spacy_fallback)
                        logger.info(f"✅ Downloaded and loaded {_spacy_fallback}")
            except Exception as e:
                logger.error(f"❌ Failed to load spaCy: {e}")
                self._spacy_nlp = None
        return self._spacy_nlp

    def _get_sentence_transformer(self):
        """Lazy load sentence transformer for semantic similarity"""
        if self._sentence_transformer is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info("🔧 Loading Sentence Transformer...")
                # Use a lightweight but effective model
                self._sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("✅ Loaded all-MiniLM-L6-v2 sentence transformer")
            except Exception as e:
                logger.error(f"❌ Failed to load sentence transformer: {e}")
                self._sentence_transformer = None
        return self._sentence_transformer

    def _get_qa_pipeline(self):
        """Lazy load question-answering pipeline for context extraction"""
        if self._qa_pipeline is None:
            try:
                from transformers import pipeline

                logger.info("🔧 Loading QA pipeline...")
                self._qa_pipeline = pipeline(
                    "question-answering",
                    model="distilbert-base-cased-distilled-squad",
                    device=-1  # CPU
                )
                logger.info("✅ Loaded distilbert QA pipeline")
            except Exception as e:
                logger.error(f"❌ Failed to load QA pipeline: {e}")
                self._qa_pipeline = None
        return self._qa_pipeline
    
    # ===== NLTK COMPONENTS =====

    _wordnet_lemmatizer = WordNetLemmatizer()

    @staticmethod
    def _sent_tokenize(text):
        """Split text into sentences using NLTK Punkt tokenizer.

        Handles abbreviations (Dr., e.g., U.S.), decimal numbers (1.5x),
        and other edge cases that naive .split('.') mangles.  Falls back
        to a regex splitter if NLTK data is unavailable.
        """
        if not text:
            return []
        try:
            return [s.strip() for s in sent_tokenize(text) if s.strip()]
        except Exception:
            # Fallback: split on sentence-ending punctuation + whitespace
            parts = re.split(r'(?<=[.!?])\s+', text)
            return [s.strip() for s in parts if s.strip()]

    @staticmethod
    def _get_wordnet_pos(treebank_tag):
        """Map Penn Treebank POS tag to WordNet POS for lemmatization."""
        if treebank_tag.startswith('J'):
            return wordnet.ADJ
        elif treebank_tag.startswith('V'):
            return wordnet.VERB
        elif treebank_tag.startswith('R'):
            return wordnet.ADV
        return wordnet.NOUN

    @classmethod
    def _lemmatize_word(cls, word):
        """Lemmatize a single word using POS-aware WordNet lemmatizer."""
        try:
            tag = pos_tag([word])[0][1]
            return cls._wordnet_lemmatizer.lemmatize(word.lower(), cls._get_wordnet_pos(tag))
        except Exception:
            return word.lower()

    @staticmethod
    def _get_wordnet_antonyms(word):
        """Return a list of antonyms for a word from WordNet.

        Searches across all synsets/lemmas for the word and collects
        unique antonym surface forms.
        """
        antonyms = set()
        for syn in wordnet.synsets(word):
            for lemma in syn.lemmas():
                for ant in lemma.antonyms():
                    antonyms.add(ant.name().replace('_', ' '))
        return list(antonyms)

    @staticmethod
    def _get_wordnet_distractors(keyword, count=3):
        """Generate plausible MCQ distractors via WordNet taxonomy.

        Returns co-hyponyms (siblings sharing the same hypernym) and
        direct hyponyms — terms related enough to be plausible but
        taxonomically distinct from the correct answer.
        """
        distractors = set()
        for syn in wordnet.synsets(keyword):
            # Co-hyponyms: siblings in the taxonomy
            for hypernym in syn.hypernyms():
                for hyponym in hypernym.hyponyms():
                    name = hyponym.lemmas()[0].name().replace('_', ' ')
                    if name.lower() != keyword.lower():
                        distractors.add(name)
            # Direct hyponyms (more specific terms)
            for hypo in syn.hyponyms():
                name = hypo.lemmas()[0].name().replace('_', ' ')
                if name.lower() != keyword.lower():
                    distractors.add(name)
        return list(distractors)[:count]

    @staticmethod
    def _is_too_generic_wordnet(word, max_depth=4):
        """Reject words whose first synset is too high in the hypernym tree.

        Words near the root of WordNet's taxonomy (entity, object, thing)
        are too generic to make good exam keywords or distractors.
        """
        try:
            synsets = wordnet.synsets(word, pos=wordnet.NOUN)
            if not synsets:
                return False
            paths = synsets[0].hypernym_paths()
            if paths:
                depth = min(len(p) for p in paths)
                return depth <= max_depth
        except Exception:
            pass
        return False

    def reset_question_tracking(self):
        """Reset tracking for new exam"""
        self.generated_questions = set()
        self.used_answers        = set()
        self._pearson_generated  = False
        # Reset per-exam speed caches
        self._keyword_cache    = {}
        self._q_embed_texts    = []
        self._q_embed_matrix   = None
        # Math mode state
        self._math_mode        = False
        self._math_sentences   = []
        self._math_concepts    = {}
        # Module distribution state
        self._module_question_targets = {}
        self._module_question_usage = {}
    
    def _normalize_text(self, text):
        """Basic text normalization.

        Blank markers (______) are converted to the literal token BLANKTOKEN before
        stripping punctuation so that fill-in-blank and MCQ questions are NOT
        treated as near-duplicates of True/False questions that use the same source
        sentence (the blank position accounts for ~10% Jaccard difference, which is
        enough to stay below the 0.9 rejection threshold).
        """
        if not text:
            return ""
        text = text.lower().strip()
        # Replace blank markers before stripping so they remain distinct words
        text = re.sub(r'_{3,}', 'BLANKTOKEN', text)
        text = re.sub(r'[^\w\s]', '', text)
        text = ' '.join(text.split())
        return text

    @staticmethod
    def _has_spacing_artifact(text):
        """Detect char-per-line or space-per-character OCR artifacts."""
        if not text:
            return False
        text = str(text)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 8:
            single_alpha_lines = sum(1 for ln in lines if len(ln) == 1 and ln.isalpha())
            if single_alpha_lines / len(lines) > 0.35:
                return True

        words = text.split()
        if len(words) >= 10:
            single_alpha_words = sum(1 for w in words if len(w) == 1 and w.isalpha())
            if single_alpha_words / len(words) > 0.35:
                return True
        return False

    @staticmethod
    def _has_text_artifact(text):
        """Detect OCR, metadata, and slide artifacts that should not reach questions."""
        if not text:
            return False
        text = str(text)
        normalized = re.sub(r'\s+', ' ', text).strip().lower()

        if ExamGenerator._has_spacing_artifact(text):
            return True
        if re.search(r'[\u2022\u25cf\u25e6\u25aa\u25a0\u25a1\u25c6\u25c7\u25ba\u25b6\u25c4\u25c0\uf0b7\uf075]', text):
            return True
        if re.search(r'\b(?:add\s+your\s+website|website|learning\s+competenc(?:y|ies)|'
                     r'at\s+the\s+end\s+of\s+the\s+session|expected\s+to|general\s*education|'
                     r'department|module|lesson|share\s+policies|pambayangdalubhasaan|'
                     r'socialsciences|nstp)\b', normalized, re.IGNORECASE):
            return True
        if re.search(r'\b[A-Z]{2,8}/\d{2}/\d{2}/\d{4}\b', text):
            return True
        if re.search(r'\bPage\s+\d+\s+of\s+\d+\b', text, re.IGNORECASE):
            return True
        if any(len(w.rstrip(".,;:!?'\"")) > 25 and w.rstrip(".,;:!?'\"").isalpha() for w in text.split()):
            return True
        return False

    def _sanitize_generated_text(self, text):
        """Repair OCR artifacts in generated stems, answers, and options."""
        if not text:
            return ""

        raw_original = str(text).replace('\r', '\n')
        raw_original = re.sub(r'[\u2022\u25cf\u25e6\u25aa\u25a0\u25a1\u25c6\u25c7\u25ba\u25b6\u25c4\u25c0\uf0b7\uf075]', ' ', raw_original)
        raw_fixed = self._fix_spaced_characters(raw_original)

        candidates = []
        for source in (raw_original, raw_fixed):
            whole = re.sub(r'\s+', ' ', self._desquish_long_tokens(source)).strip()
            if whole:
                candidates.append(whole)
            for line in source.splitlines():
                cleaned = self._fix_spaced_characters(line)
                cleaned = self._desquish_long_tokens(cleaned)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                if cleaned:
                    candidates.append(cleaned)

        if not candidates:
            candidates = [self._desquish_long_tokens(raw_original)]

        if len(candidates) > 1:
            non_single = [c for c in candidates if not (len(c) == 1 and c.isalpha())]
            if non_single:
                candidates = non_single

        deduped = []
        seen = set()
        for candidate in candidates:
            norm = self._normalize_text(candidate)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            deduped.append(candidate)

        if not deduped:
            deduped = [re.sub(r'\s+', ' ', self._desquish_long_tokens(raw_original)).strip()]

        def _quality_score(value):
            score = len(value.split())
            if value.endswith('?') or value.endswith('.'):
                score += 2
            if ExamGenerator._has_text_artifact(value):
                score -= 12
            if re.search(r'\b(?:which|what|how|why|when|where)\b', value, re.IGNORECASE):
                score += 3
            score -= max(len(value) - 180, 0) / 20.0
            return score

        best = max(deduped, key=_quality_score)
        best = re.sub(r'\s+', ' ', best).strip()

        # Collapse hallucinatory spaced-letter artifacts that sometimes appear when
        # OCR / generation produces each character separated by whitespace.
        # Example: "W h i c h   c o n c e p t" → "Which concept".
        best = re.sub(
            r'(?<!\w)(?:[A-Za-z]\s){4,}[A-Za-z](?!\w)',
            lambda m: m.group(0).replace(' ', ''),
            best
        )
        return best

    def _is_low_quality_objective_answer(self, answer, question_type=None):
        """Reject generic or artifact-laden answers for objective questions."""
        cleaned = self._sanitize_generated_text(answer).strip()
        if not cleaned:
            return True
        if self._has_text_artifact(cleaned):
            return True
        if re.search(r'https?://|www\.', cleaned, re.IGNORECASE):
            return True
        if len(cleaned.split()) > 8:
            return True
        if len(cleaned.split()) == 1 and len(cleaned) < 3:
            return True

        normalized = cleaned.lower()
        generic_terms = {
            'student', 'students', 'course', 'study', 'session', 'module',
            'lesson', 'website', 'department', 'school', 'teacher', 'teachers',
            'example', 'examples', 'following', 'statement', 'statements',
            'activity', 'activities', 'chapter', 'unit', 'topic', 'topics',
        }
        if normalized in generic_terms:
            return True

        strict_types = {'multiple_choice', 'identification', 'true_false'}
        if question_type in strict_types:
            too_generic = {
                'rules', 'rule', 'behavior', 'conduct', 'area', 'areas', 'theories',
                'theory', 'principles', 'principle', 'people', 'person', 'thing',
                'things', 'part', 'parts', 'value', 'values', 'study', 'course',
            }
            if normalized in too_generic:
                return True

        return False

    def _is_low_quality_clue(self, clue):
        """Reject clues that are likely headers, learning outcomes, or OCR debris."""
        clue = self._sanitize_generated_text(clue)
        if not clue:
            return True
        if self._has_text_artifact(clue):
            return True
        if len(clue.split()) < 4 or len(clue.split()) > 24:
            return True
        if re.search(r'\b(?:this\s+course|at\s+the\s+end\s+of\s+the\s+session|'
                     r'expected\s+to|learning\s+competenc(?:y|ies)|share\s+policies|'
                     r'add\s+your\s+website)\b', clue, re.IGNORECASE):
            return True
        return False

    # ===== AI ENHANCEMENT: Advanced NLP Methods =====

    def _extract_linguistic_features(self, text):
        """
        AI ENHANCEMENT: Extract linguistic features using spaCy
        Returns: dict with POS tags, entities, noun phrases, verb phrases
        """
        nlp = self._get_spacy_nlp()
        if not nlp or not text:
            return None

        try:
            doc = nlp(text[:1000000])  # Limit to 1M chars for performance

            features = {
                'noun_phrases': [chunk.text for chunk in doc.noun_chunks],
                'verb_phrases': [token.text for token in doc if token.pos_ == 'VERB'],
                'named_entities': [(ent.text, ent.label_) for ent in doc.ents],
                'important_nouns': [token.text for token in doc if token.pos_ == 'NOUN' and len(token.text) > 3],
                'adjectives': [token.text for token in doc if token.pos_ == 'ADJ'],
                'key_subjects': [token.text for token in doc if token.dep_ in ('nsubj', 'nsubjpass')],
                'key_objects': [token.text for token in doc if token.dep_ in ('dobj', 'pobj')]
            }

            logger.info(f"🧠 Extracted linguistic features: {len(features['noun_phrases'])} NPs, "
                       f"{len(features['named_entities'])} entities")
            return features

        except Exception as e:
            logger.error(f"❌ Error extracting linguistic features: {e}")
            return None

    def _get_semantic_similarity(self, text1, text2):
        """
        AI ENHANCEMENT: Calculate semantic similarity using sentence transformers
        Returns: float similarity score (0-1)
        """
        transformer = self._get_sentence_transformer()
        if not transformer or not text1 or not text2:
            return 0.0

        try:
            embeddings = transformer.encode([text1, text2])
            # Cosine similarity — guard against zero-norm embeddings
            norm_product = np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            if norm_product == 0:
                return 0.0
            similarity = np.dot(embeddings[0], embeddings[1]) / norm_product
            return float(similarity)

        except Exception as e:
            logger.error(f"❌ Error calculating semantic similarity: {e}")
            return 0.0

    def _extract_answer_from_context(self, context, question):
        """
        AI ENHANCEMENT: Use QA pipeline to extract precise answers
        """
        qa_pipeline = self._get_qa_pipeline()
        if not qa_pipeline or not context or not question:
            return None

        try:
            result = qa_pipeline(question=question, context=context)
            if result and result.get('score', 0) > 0.5:
                return result['answer']
        except Exception as e:
            logger.error(f"❌ Error in QA extraction: {e}")

        return None

    def _enhance_keyword_selection_with_nlp(self, text, tfidf_keywords):
        """
        AI ENHANCEMENT: Enhance TF-IDF keywords with spaCy linguistic analysis
        Prioritizes: named entities, noun phrases, domain-specific terms
        Result is cached per text so multiple question types re-use one spaCy parse.
        """
        cache_key = hash(text[:200])
        if cache_key in self._keyword_cache:
            return self._keyword_cache[cache_key]

        nlp = self._get_spacy_nlp()
        if not nlp:
            return tfidf_keywords

        try:
            doc = nlp(text[:int(os.getenv("AI_SPACY_MAX_CHUNK_CHARS", "100000"))])

            # Extract linguistically important terms
            linguistic_keywords = set()

            # 1. Named entities (high priority)
            for ent in doc.ents:
                if len(ent.text) > 2 and ent.label_ in ['PERSON', 'ORG', 'GPE', 'PRODUCT', 'EVENT', 'LAW', 'NORP']:
                    linguistic_keywords.add(ent.text.lower())

            # 2. Noun chunks (medium priority)
            for chunk in doc.noun_chunks:
                if 2 <= len(chunk.text.split()) <= 3:  # Prefer 2-3 word phrases
                    linguistic_keywords.add(chunk.text.lower())

            # 3. Technical terms (compound nouns)
            for token in doc:
                if token.pos_ == 'NOUN' and token.dep_ == 'compound':
                    compound = f"{token.text} {token.head.text}"
                    linguistic_keywords.add(compound.lower())

            # Merge with TF-IDF keywords
            tfidf_set = {kw.lower() for kw, _ in tfidf_keywords}
            enhanced_keywords = []

            # Prioritize keywords that appear in both
            for kw in linguistic_keywords:
                if any(kw in tfidf_kw or tfidf_kw in kw for tfidf_kw in tfidf_set):
                    enhanced_keywords.append((kw, 1.0))  # High score

            # Add remaining TF-IDF keywords
            for kw, score in tfidf_keywords:
                if kw.lower() not in linguistic_keywords:
                    enhanced_keywords.append((kw, score * 0.8))  # Slightly lower score

            filtered_keywords = []
            seen = set()
            for kw, score in enhanced_keywords:
                cleaned_kw = self._sanitize_generated_text(kw).strip()
                norm = cleaned_kw.lower()
                if not cleaned_kw or norm in seen:
                    continue
                if self._has_text_artifact(cleaned_kw):
                    continue
                if self._is_low_quality_objective_answer(cleaned_kw, question_type='multiple_choice'):
                    continue
                seen.add(norm)
                filtered_keywords.append((cleaned_kw, score))

            logger.info(f"🎯 Enhanced keywords: {len(filtered_keywords)} total "
                       f"({len(linguistic_keywords)} from NLP, {len(tfidf_keywords)} from TF-IDF)")

            result = sorted(filtered_keywords, key=lambda x: x[1], reverse=True)
            self._keyword_cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"❌ Error enhancing keywords with NLP: {e}")
            return tfidf_keywords
    
    def _is_near_duplicate(self, question_text):
        """Check for near-duplicate questions using Jaccard + semantic similarity"""
        normalized = self._normalize_text(question_text)

        if not normalized or len(normalized) < 5:
            return True

        if normalized in self.generated_questions:
            return True

        new_words = set(normalized.split())
        # Jaccard loop is O(N) per call → O(N²) total over an exam.
        # When the accepted-question set exceeds 1000, skip it and rely solely
        # on the semantic matrix dot-product below, which is already O(1) per check.
        if len(self.generated_questions) <= 1000:
            for existing_q in self.generated_questions:
                existing_words = set(existing_q.split())

                if len(existing_words) == 0 or len(new_words) == 0:
                    continue

                overlap = len(existing_words & new_words)
                similarity = overlap / max(len(existing_words), len(new_words))

                if similarity > 0.92:
                    return True

        # Semantic pass: single encode of new question, dot-product against cached matrix
        try:
            st = self._get_sentence_transformer()
            if st and self._q_embed_matrix is not None and len(self._q_embed_texts) > 0:
                new_emb = st.encode([question_text], show_progress_bar=False)[0]
                new_norm = np.linalg.norm(new_emb)
                if new_norm > 0:
                    sims = self._q_embed_matrix.dot(new_emb) / (
                        np.linalg.norm(self._q_embed_matrix, axis=1) * new_norm + 1e-9
                    )
                    if float(sims.max()) > 0.90:
                        return True
        except Exception:
            pass

        return False
    
    def _add_question_if_valid(self, question):
        """Validate and track question"""
        if not question or not question.get('question_text'):
            return False

        question_text = self._sanitize_generated_text(question['question_text'])
        question['question_text'] = question_text
        q_type = question.get('question_type')
        ans = question.get('correct_answer')
        if isinstance(ans, str):
            ans = self._sanitize_generated_text(ans)
            question['correct_answer'] = ans

        if isinstance(question.get('options'), list):
            question['options'] = [
                self._sanitize_generated_text(opt) if isinstance(opt, str) else opt
                for opt in question['options']
            ]

        if q_type in ['multiple_choice', 'true_false', 'fill_in_blank', 'identification']:
            if self._has_text_artifact(question_text):
                return False

        if ans and isinstance(ans, str):
            ans_clean = ans.strip()
            # Early reject answer leakage for objective types before verification
            if q_type in ['multiple_choice', 'fill_in_blank', 'identification']:
                if len(ans_clean) > 3 and re.search(re.escape(ans_clean), question_text, flags=re.IGNORECASE):
                    return False
            if q_type in ['multiple_choice', 'identification', 'true_false']:
                if self._is_low_quality_objective_answer(ans_clean, question_type=q_type):
                    return False
        
        if len(question_text.strip()) < 5:
            return False
        
        if self._is_near_duplicate(question_text):
            return False
        
        self.generated_questions.add(self._normalize_text(question_text))
        if question.get('correct_answer'):
            self.used_answers.add(question['correct_answer'])

        # Update embedding matrix for fast O(1) duplicate detection on next question
        try:
            st = self._get_sentence_transformer()
            if st:
                emb = st.encode([question_text], show_progress_bar=False)  # shape (1, D)
                self._q_embed_texts.append(question_text)
                if self._q_embed_matrix is None:
                    self._q_embed_matrix = emb
                else:
                    self._q_embed_matrix = np.vstack([self._q_embed_matrix, emb])
        except Exception:
            pass

        return True
    
    def _extract_text_content(self, module_content):
        """Extract text from module content"""
        if not module_content:
            return ""
        if isinstance(module_content, str):
            return module_content.strip()
        if isinstance(module_content, list):
            text_parts = []
            for item in module_content:
                if isinstance(item, dict):
                    text_parts.append(str(item.get('content_text', '')))
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts)
        if isinstance(module_content, dict):
            collected = []
            for v in module_content.values():
                if isinstance(v, str):
                    collected.append(v)
                elif isinstance(v, list):
                    for x in v:
                        if isinstance(x, str):
                            collected.append(x)
            return "\n".join(collected)
        return ""
    
    def _extract_topics(self, module_content):
        """Extract topics from content"""
        text = self._extract_text_content(module_content)
        self.tfidf_engine.add_document(text)
        keywords = self.tfidf_engine.extract_keywords(text, top_n=15)
        return [k for k, _ in keywords]
    
    @staticmethod
    def _fix_spaced_characters(text):
        """
        Fix two PDF extraction artifacts where text is stored character-by-character.

        Type 1 — newline-per-character (most common in scanned/OCR PDFs):
            "C\\no\\nm\\np\\nl\\ne\\nt\\ne\\n\\nt\\nh\\ne" → "Complete the"
            Detection: >45% of lines in a paragraph are a single character.
            Word breaks are signalled by empty lines between single-char runs.
            When NO empty-line separators exist, wordninja is used to segment
            the concatenated characters into proper words.

        Type 2 — space-per-character (less common):
            "C o m p l e t e" → "Complete"
            Detection: runs of 4+ single letters separated by single spaces.

        Processing is done paragraph-by-paragraph so mixed documents (some normal
        paragraphs, some character-per-line paragraphs) are handled correctly.
        """
        try:
            import wordninja as _wn
            _wordninja_available = True
        except ImportError:
            _wn = None
            _wordninja_available = False

        def _segment_if_squished(token):
            """
            If a token is longer than 20 chars and wordninja is available,
            split it into dictionary words. Otherwise return it as-is.
            """
            if _wordninja_available and len(token) > 20:
                parts = _wn.split(token)
                # Only accept the split if it actually produces multiple words
                # and doesn't mangle proper nouns / acronyms badly
                if len(parts) > 1:
                    return parts
            return [token]

        # Split into paragraphs on 2+ consecutive newlines
        paragraphs = re.split(r'\n{2,}', text)
        fixed = []

        for para in paragraphs:
            lines = para.split('\n')
            total = len(lines)
            if total == 0:
                fixed.append(para)
                continue

            single_char = sum(1 for l in lines if len(l.strip()) == 1)

            if total >= 2 and single_char / total > 0.45:
                # ── Type 1: newline-per-character ────────────────────────────
                # Each letter is on its own line; empty lines = word breaks.
                words = []
                current_chars = []
                for line in lines:
                    c = line.strip()
                    if len(c) == 1:
                        current_chars.append(c)
                    else:
                        if current_chars:
                            joined = ''.join(current_chars)
                            # Skip multi-char line if it is just a squished copy of
                            # the accumulated chars (PDF stores both raw glyphs AND
                            # a concatenated text-layer version of the same sentence).
                            c_alpha = re.sub(r'[^A-Za-z0-9]', '', c).lower()
                            joined_alpha = re.sub(r'[^A-Za-z0-9]', '', joined).lower()
                            is_squished_duplicate = (
                                c_alpha == joined_alpha
                                or (len(c_alpha) > 10 and joined_alpha.startswith(c_alpha[:10]))
                            )
                            words.extend(_segment_if_squished(joined))
                            current_chars = []
                            if c and not is_squished_duplicate:
                                words.extend(_segment_if_squished(c))
                        elif c:  # no accumulated chars, standalone multi-char token
                            words.extend(_segment_if_squished(c))
                if current_chars:
                    joined = ''.join(current_chars)
                    words.extend(_segment_if_squished(joined))
                fixed.append(' '.join(words))

            else:
                # ── Type 2: space-per-character ──────────────────────────────
                # "C o m p l e t e" → "Complete"
                # Require 4+ chars to avoid false-positives on "I am" etc.
                fixed_para = re.sub(
                    r'(?<!\w)([A-Za-z] ){4,}[A-Za-z](?!\w)',
                    lambda m: m.group(0).replace(' ', ''),
                    para
                )
                fixed.append(fixed_para)

        # ── Final pass: split any remaining squished tokens with wordninja ──
        # Catches: Type 2 output, pre-squished DB text, and any missed Type 1
        result = '\n\n'.join(fixed)
        if _wordninja_available:
            def _split_squished(m):
                token = m.group(0)
                # Strip trailing punctuation before splitting
                trail = ''
                while token and not token[-1].isalnum():
                    trail = token[-1] + trail
                    token = token[:-1]
                if len(token) > 15:
                    parts = _wn.split(token)
                    if len(parts) > 1:
                        return ' '.join(parts) + trail
                return m.group(0)
            # Match any token with 16+ consecutive alpha chars (possibly followed by punctuation)
            result = re.sub(r'[A-Za-z]{16,}[^\s]*', _split_squished, result)
        return result


    def _clean_text_for_questions(self, text):
        """
        Clean raw module text before sentence splitting.

        Removes line-by-line noise so that sentence splitting never picks up:
        - URLs / web links
        - Bullet-point list lines
        - ALL-CAPS section headers (ASSESSMENT, PRACTICE EXERCISES, etc.)
        - Reference / page-number lines
        - Lesson plan structural labels
        - Roman numerals and numbered list prefixes
        """
        if not text:
            return ""

        # Fix spaced-out characters from PDF extraction before anything else
        text = self._fix_spaced_characters(text)

        # Fix PDF doubled-char artifacts (distinct from char-per-line):
        #   word-initial doubled consonant: "sshould"→"should", "ffirst"→"first"
        #   word-initial doubled i/u:       "iin-step"→"in-step", "uunder"→"under"
        #   word-final doubled vowel:       "Polkaa"→"Polka", "steppee"→"steppe"
        text = re.sub(r'(?<!\w)([bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ])\1(?=[a-zA-Z]+)', r'\1', text)
        text = re.sub(r'(?<!\w)([iuIU])\1(?=[a-zA-Z]+)', r'\1', text)
        text = re.sub(r'([aeiouAEIOU])\1(?!\w)', r'\1', text)

        cleaned_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append('')
                continue

            # Drop lines that are just URLs or contain only a URL
            if re.search(r'https?://\S+|www\.\S+', stripped):
                continue

            # Drop lines starting with a math operator or Greek letter
            # In math mode: only drop if the line has NO English words (pure notation noise)
            if re.match(r'^\s*[=<>≤≥±∓]', stripped) or \
               re.match(r'^\s*[αβγδεζηθικλμνξπρστυφχψωΩΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ]', stripped):
                if not getattr(self, '_math_mode', False):
                    continue
                # Math mode: keep lines with ≥2 English words (≥3 chars each)
                eng_words = re.findall(r'[a-zA-Z]{3,}', stripped)
                if len(eng_words) < 2:
                    continue

            # Drop bullet-point list lines (start with dash/bullet or have ≥2 " - ")
            if re.match(r'^[-•]\s', stripped) or stripped.count(' - ') >= 2:
                continue

            # Drop lines whose first word (≥4 chars) is all-caps — section headers
            first_word = stripped.split()[0] if stripped.split() else ''
            if len(first_word) >= 4 and first_word.isupper() and not first_word.isdigit():
                continue

            # Drop reference / page-number lines
            if re.search(r'\bPage\s+\d+\s+of\s+\d+\b|\bREFERENCES?\b|\bBIBLIOGRAPHY\b',
                         stripped, re.IGNORECASE):
                continue

            # Drop answer-key / exercise-sheet lines
            # e.g. "1. __________ (Correct Answer)" / "Answer: x = 5" / "Ans." / all-underscores
            if re.search(r'\(correct\s+answer\)', stripped, re.IGNORECASE):
                continue
            if re.match(r'^\s*ans(?:wer)?[\s.:]+', stripped, re.IGNORECASE):
                continue
            # Lines that are ≥ 40 % underscores/dashes (blank-fill exercise lines)
            non_space = stripped.replace(' ', '')
            if non_space and (non_space.count('_') + non_space.count('-')) / len(non_space) >= 0.4:
                continue

            cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines)

        # Remove inline lesson plan header words that may remain mid-sentence
        lesson_headers = [
            r'PRELIMINARY ACTIVITIES', r'LESSON PROPER', r'MOTIVATION',
            r'PRESENTATION', r'DISCUSSION', r'GENERALIZATION', r'APPLICATION',
            r'EVALUATION', r'ASSIGNMENT', r'REVIEW', r'INTRODUCTION',
            r'DEVELOPMENT', r'OBJECTIVES?', r'LEARNING COMPETENC(Y|IES)',
            r'SUBJECT MATTER', r'MATERIALS?', r'PROCEDURE', r'CLOSING',
            r'PRACTICE EXERCISES?(?:/ACTIVITIES)?', r'ASSESSMENT',
            r'ADDITIONAL RESOURCES?',
        ]
        for header in lesson_headers:
            text = re.sub(r'\b' + header + r'\b', '', text, flags=re.IGNORECASE)

        # Remove common slide bullets, OCR glyphs, and decorative symbols that leak
        # into clues and produce malformed stems.
        text = re.sub(r'[\u2022\u25cf\u25e6\u25aa\u25a0\u25a1\u25c6\u25c7\u25ba\u25b6\u25c4\u25c0\uf0b7\uf075]', ' ', text)
        text = re.sub(r'[✔✓]+', ' ', text)

        # Unwrap [EQUATION: ...] OMML tags — replace with just the inner expression
        # so question text reads "α" instead of "[EQUATION: α]"
        text = ExamGenerator._clean_equation_text(text)

        # Remove Roman numerals at start of lines — period+space required to avoid
        # stripping capital letters that legitimately start sentences (e.g. "I think...")
        text = re.sub(r'^\s*[IVXLCDM]+\.\s+', '', text, flags=re.MULTILINE)

        # Remove numbered list prefixes only (1. text, 2. text)
        # Single capital letters (A. text) are intentionally excluded to avoid
        # stripping the first letter of legitimate sentences (e.g. "T. he" → "he")
        text = re.sub(r'^\s*[0-9]+\.\s+', '', text, flags=re.MULTILINE)

        # Collapse whitespace (this converts any surviving Type-1 newline-per-char
        # artifacts into Type-2 space-per-char format: "t\nh\ne" → "t h e")
        text = re.sub(r'\s+', ' ', text)

        # Second-pass Type-2 fix: after whitespace collapse, runs of single letters
        # separated by spaces ("t h e r e a r e ...") are joined into one token.
        # _fix_spaced_characters ran on the raw text before the collapse, so any
        # Type-1 sections that survived now appear as Type-2 and need this pass.
        text = re.sub(
            r'(?<!\w)([A-Za-z] ){4,}[A-Za-z](?!\w)',
            lambda m: m.group(0).replace(' ', ''),
            text
        )

        return text.strip()

    @staticmethod
    def _desquish_long_tokens(text):
        """
        Split abnormally long alphanumeric tokens (e.g., 'thisisaconcatenatedsentence')
        into word-like pieces so they render with spaces in the UI. Uses wordninja when
        available; otherwise falls back to simple heuristic chunking.
        """
        if not text:
            return text

        try:
            import wordninja
            splitter = wordninja.split
            has_wordninja = True
        except ImportError:
            splitter = None
            has_wordninja = False

        stopwords = {
            'the', 'and', 'to', 'of', 'in', 'for', 'with', 'on', 'that', 'this', 'these', 'those',
            'is', 'are', 'was', 'were', 'not', 'network', 'routing', 'update', 'updates',
            'traffic', 'data', 'communication', 'device', 'media', 'internet', 'broadcast',
            'entire', 'address', 'frame', 'router', 'route', 'mac', 'ip'
        }
        question_chunks = [
            'which', 'what', 'when', 'where', 'why', 'how',
            'concept', 'idea', 'term', 'statement', 'option',
            'would', 'should', 'could', 'most', 'best', 'important',
            'relevant', 'judging', 'evaluating', 'analyzing', 'examining',
            'case', 'situation', 'involving', 'moral', 'ethical', 'standards',
        ]

        def _greedy_stop_split(tok: str):
            lower = tok.lower()
            i = 0
            parts = []
            sw_list = sorted(stopwords, key=len, reverse=True)
            while i < len(tok):
                matched = None
                for sw in sw_list:
                    if lower.startswith(sw, i):
                        matched = tok[i:i+len(sw)]
                        break
                if matched:
                    parts.append(matched)
                    i += len(matched)
                else:
                    parts.append(tok[i:i+6])
                    i += 6
            return [p for p in parts if p]

        fixed_tokens = []
        for tok in text.split():
            leading = re.match(r'^\W+', tok)
            trailing = re.search(r'\W+$', tok)
            lead = leading.group(0) if leading else ''
            trail = trailing.group(0) if trailing else ''
            core_end = len(tok) - len(trail) if trail else len(tok)
            core = tok[len(lead):core_end]

            if len(core) > 20 and core.isalpha():
                if has_wordninja:
                    parts = splitter(core)
                    if len(parts) > 1:
                        if lead:
                            parts[0] = f"{lead}{parts[0]}"
                        if trail:
                            parts[-1] = f"{parts[-1]}{trail}"
                        fixed_tokens.extend(parts)
                        continue
                # fallback: greedy stopword split; if still single chunk, chunk by pattern
                parts = _greedy_stop_split(core)
                if len(parts) <= 1:
                    questionish = core
                    for chunk in question_chunks:
                        questionish = re.sub(
                            rf'(?i){chunk}',
                            lambda m: f" {m.group(0)} ",
                            questionish
                        )
                    questionish = re.sub(r'\s+', ' ', questionish).strip()
                    if ' ' in questionish:
                        parts = questionish.split()
                if len(parts) <= 1:
                    parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+|.{1,8}', core)
                if lead and parts:
                    parts[0] = f"{lead}{parts[0]}"
                if trail and parts:
                    parts[-1] = f"{parts[-1]}{trail}"
                fixed_tokens.extend([p for p in parts if p])
            else:
                fixed_tokens.append(tok)

        return ' '.join(fixed_tokens)

    @staticmethod
    def _is_valid_question_sentence(s):
        """
        Return True only when a sentence is suitable as a question stem.

        Rejects:
        - Bullet-point blobs  (≥2 occurrences of " - " or "• ")
        - Lines starting with an ALL-CAPS word (section headers that bled through)
        - Sentences containing URLs
        - Exercise instruction sentences
        - Course-code strings (e.g. CS32-ATFL)
        - Reference / page-number fragments
        """
        if not s or len(s.split()) < 5:
            return False

        # Reject squished/concatenated text (PDF char-per-line artifact not fully repaired)
        # e.g. "Themasteryofthesepositionsisessential" — a single token > 25 chars
        # that contains no digits and no hyphens is almost certainly a PDF extraction error.
        words = s.split()
        if any(len(w.rstrip(".,;:!?'\"")) > 25 and w.rstrip(".,;:!?'\"").isalpha() for w in words):
            return False

        # Reject space-per-character artifacts (Type-2 PDF artifact that slipped through):
        # sentences where ≥40% of tokens are single alphabetic characters, e.g.
        # "t h e r e a r e f o u r p o s s i b l e o u t c o m e s ..."
        if len(words) >= 10:
            single_alpha = sum(1 for w in words if len(w) == 1 and w.isalpha())
            if single_alpha / len(words) > 0.40:
                return False

        # Bullet blob
        if s.count(' - ') >= 2 or s.count('• ') >= 2:
            return False

        # ALL-CAPS leading word:
        # keep rejecting short header-like lines, but allow full sentences that
        # begin with acronyms (e.g., "TCP uses ...").
        tokens = s.strip().split()
        first = tokens[0]
        if len(first) >= 4 and first.isupper() and len(tokens) <= 4:
            return False

        # URLs
        if re.search(r'https?://\S+|www\.\S+', s):
            return False

        # Exercise/instruction patterns (generic worksheet headers)
        # NOTE: keep patterns narrow so math problem sentences are NOT rejected:
        #   "Solve the equation 3x + 2 = 8"  → valid math question (no "following")
        #   "Answer the question using..."   → valid (no "following")
        #   "Solve the following problems:"  → exercise header → reject
        if re.search(
            r'^\s*(?:write\s+the|evaluate\s+the\s+following|fill\s+in|'
            r'answer\s+the\s+following|solve\s+the\s+following|complete\s+the|choose\s+the|'
            r'match\s+the|list\s+the|draw\s+the|to\s+be\s+given|'
            r'to\s+be\s+submitted|true\s+or\s+false|directions?:|'
            r'instructions?:|this\s+module)',
            s, re.IGNORECASE
        ):
            return False

        # Course codes
        if re.search(r'\b[A-Z]{2,6}\d{1,3}[-–]\w+\b', s):
            return False

        # Reference / page fragments
        if re.search(r'\bPage\s+\d+\s+of\s+\d+\b|\bREFERENCES?\b', s, re.IGNORECASE):
            return False

        # Sentences that already contain a pre-filled blank (exercise sheets)
        if re.search(r'_{3,}', s):
            return False

        # Sentences that expose an answer inline
        if re.search(r'\(correct\s+answer\)|correct\s+answer\s*:', s, re.IGNORECASE):
            return False
        if re.match(r'^\s*ans(?:wer)?[\s.:]+', s, re.IGNORECASE):
            return False

        # Sentences starting with a math operator (hypothesis notation that bled through)
        if re.match(r'^\s*[=<>≤≥±∓]', s):
            return False

        # Sentences starting with a Greek letter (formula artifacts)
        if re.match(r'^\s*[αβγδεζηθικλμνξπρστυφχψωΩΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ]', s):
            return False

        # Decimal split fragments — keep this narrow so we do not reject valid
        # quantified statements like "5 samples were collected ...".
        if re.match(r'^\s*\d{1,2}\s+[a-z]\w*$', s.strip()) and len(words) <= 4:
            return False

        # Sentences containing empty parentheses (keyword removed from inside parens)
        if re.search(r'\(\s*\)', s):
            return False

        # Double-negative constructions produce logically ambiguous T/F statements
        # e.g. "failed not to reject", "not to reject the null", "not not"
        if re.search(
            r'\bfailed\s+not\b|\bnot\s+to\s+reject\b|\bnot\s+not\b'
            r'|\bcannot\s+not\b|\bdo\s+not\s+not\b|\bwill\s+not\s+not\b',
            s, re.IGNORECASE
        ):
            return False

        return True
    
    def _extract_definition_sentence(self, text, keyword):
        """
        CRITICAL FIX: Extract ONLY the definition sentence
        
        Rules:
        1. Must contain the keyword
        2. Must be a definition (contains "is", "are", "refers to", "means")
        3. Should NOT start with lesson headers
        4. Should be 20-200 characters
        """
        # Clean the text first
        text = self._clean_text_for_questions(text)
        
        # Split into sentences using NLTK Punkt tokenizer
        sentences = self._sent_tokenize(text)
        
        # Definition indicators
        definition_patterns = [
            r'\bis\s+(a|an|the)\s+',
            r'\bare\s+',
            r'\brefers?\s+to\s+',
            r'\bmeans?\s+',
            r'\bdefined\s+as\s+',
            r'\bknown\s+as\s+',
            r'\bcalled\s+'
        ]
        
        best_sentence = None
        best_score = 0
        
        for sentence in sentences:
            sentence = sentence.strip()

            # Skip if too short or too long
            if len(sentence) < 20 or len(sentence) > 200:
                continue

            # Reject formula-fragment sentences (same rules as question stems)
            if not ExamGenerator._is_valid_question_sentence(sentence):
                continue

            # Skip if doesn't contain keyword
            if keyword.lower() not in sentence.lower():
                continue

            # Check for definition patterns
            score = 0
            for pattern in definition_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    score += 1
            
            # Prefer sentences where keyword comes first (subject of definition)
            if sentence.lower().startswith(keyword.lower()):
                score += 2
            
            if score > best_score:
                best_score = score
                best_sentence = sentence
        
        return best_sentence
    
    def _create_clean_description(self, sentence, keyword):
        """
        CRITICAL FIX: Create clean description WITHOUT the keyword
        
        Example:
        Input: "MAC address is the physical address that identifies devices"
        Output: "the physical address that identifies devices"
        """
        if not sentence:
            return None
        
        # Pattern 1: "X is Y" → extract "Y"
        pattern1 = r'\b' + re.escape(keyword) + r'\s+is\s+(a|an|the)?\s*(.+)'
        match = re.search(pattern1, sentence, re.IGNORECASE)
        if match:
            return match.group(2).strip()
        
        # Pattern 2: "X are Y" → extract "Y"  
        pattern2 = r'\b' + re.escape(keyword) + r'\s+are\s+(.+)'
        match = re.search(pattern2, sentence, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Pattern 3: "X refers to Y" → extract "Y"
        pattern3 = r'\b' + re.escape(keyword) + r'\s+refers?\s+to\s+(.+)'
        match = re.search(pattern3, sentence, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Pattern 4: "X means Y" → extract "Y"
        pattern4 = r'\b' + re.escape(keyword) + r'\s+means?\s+(.+)'
        match = re.search(pattern4, sentence, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Fallback: remove keyword and return rest
        clean = re.sub(r'\b' + re.escape(keyword) + r'\b', '', sentence, flags=re.IGNORECASE)
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Strip leading copula/article words with regex (NOT lstrip, which strips individual
        # characters from a set and corrupts words like "the" → "he", "testing" → "g")
        clean = re.sub(
            r'^(?:is|are|was|were|refers?\s+to|means?|the|a|an)\s+',
            '', clean, flags=re.IGNORECASE
        ).strip()
        # Remove empty parentheses left when a parenthesised keyword was blanked
        clean = re.sub(r'\(\s*\)', '', clean).strip()
        # Reject if the description ends with a dangling article/preposition
        # (means the keyword was at the very end of the sentence)
        if re.search(r'\b(?:a|an|the|in|of|by|to|for|on|at|about)\s*$', clean, re.IGNORECASE):
            return None
        # Reject double-article artifacts ("( a null a hypothesis"  → broken)
        if re.search(r'\b(a|an|the)\s+(a|an|the)\b', clean, re.IGNORECASE):
            return None

        return clean if len(clean) > 15 else None

    @staticmethod
    def _normalize_clue_text(clue):
        """Normalize a clue/description fragment for use in stems."""
        clue = re.sub(r'\s+', ' ', str(clue or '')).strip()
        clue = clue.strip(' "\'')
        clue = re.sub(r'^[,;:\-\s]+|[,;:\-\s]+$', '', clue)
        clue = clue.rstrip('.')
        return clue.strip()

    @staticmethod
    def _compress_clue_text(clue, max_words=14):
        """Shorten long clue text so rewritten stems do not mirror the source sentence."""
        clue = ExamGenerator._normalize_clue_text(clue)
        if not clue:
            return None

        original = clue
        clue = re.sub(r'\([^)]*\)', '', clue)
        clue = re.sub(r'\s+', ' ', clue).strip(' ,;:-')

        split_markers = [
            r'\b(?:using|through|via|including|especially|because|since|although|while)\b',
            r'\b(?:which|who|whom|whose|where|when|that)\b',
        ]
        for marker in split_markers:
            parts = re.split(marker, clue, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2 and len(parts[0].split()) >= 4:
                clue = parts[0].strip(' ,;:-')
                break

        words = clue.split()
        if len(words) > max_words:
            clue = ' '.join(words[:max_words]).strip(' ,;:-')
            clue = re.sub(
                r'\b(?:a|an|the|and|or|of|in|on|at|for|to|with|by|from|into|onto)\s*$',
                '',
                clue,
                flags=re.IGNORECASE,
            ).strip(' ,;:-')

        if len(clue.split()) < 4:
            clue = original

        return ExamGenerator._normalize_clue_text(clue)

    def _extract_question_clue(self, text, keyword):
        """
        Return a short clue derived from module text without exposing the answer.

        Preference order:
        1. Definition sentence cleaned into a description
        2. Any valid context sentence containing the keyword
        """
        if not text or not keyword:
            return None

        clean_text = self._clean_text_for_questions(text)
        candidates = []
        definition_sentence = self._extract_definition_sentence(clean_text, keyword)
        if definition_sentence:
            candidates.append(definition_sentence)

        for sentence in self._sent_tokenize(clean_text):
            sentence = sentence.strip()
            if len(sentence) < 20 or len(sentence) > 220:
                continue
            if not ExamGenerator._is_valid_question_sentence(sentence):
                continue
            if keyword.lower() not in sentence.lower():
                continue
            candidates.append(sentence)

        seen = set()
        for sentence in candidates:
            if sentence in seen:
                continue
            seen.add(sentence)
            clue = self._create_clean_description(sentence, keyword)
            clue = self._sanitize_generated_text(clue)
            clue = self._normalize_clue_text(clue)
            clue = self._compress_clue_text(clue)
            if not clue or self._is_low_quality_clue(clue):
                continue
            if keyword.lower() in clue.lower():
                continue
            if len(clue.split()) < 4:
                continue
            if re.search(r'_{3,}', clue):
                continue
            return clue

        return None

    def _build_mcq_stem_from_clue(self, clue, bloom_level):
        """Turn a clue into a Bloom-aware MCQ stem without naming the answer."""
        clue = self._normalize_clue_text(clue)
        if not clue:
            return None

        templates = {
            'remembering': [
                "Which term best matches this description: {clue}?",
                "Which concept is being described here: {clue}?",
            ],
            'understanding': [
                "Which concept is best explained by this description: {clue}?",
                "Which idea best fits the explanation below: {clue}?",
            ],
            'applying': [
                "Which concept would be most useful in a situation involving {clue}?",
                "Which idea would best apply to a case involving {clue}?",
            ],
            'analyzing': [
                "Which concept is most central to analyzing a case involving {clue}?",
                "Which idea would be most relevant when examining a situation involving {clue}?",
            ],
            'evaluating': [
                "Which concept would be most important when judging a case involving {clue}?",
                "Which idea would be most relevant when evaluating a situation involving {clue}?",
            ],
            'creating': [
                "Which concept should guide the design of a response to a case involving {clue}?",
                "Which idea would best support creating a solution for a case involving {clue}?",
            ],
        }
        choices = templates.get(bloom_level, templates['remembering'])
        return random.choice(choices).format(clue=clue)

    def _build_fill_in_blank_stem_from_clue(self, clue, bloom_level):
        """Turn a clue into a fill-in-the-blank stem without copying the source sentence."""
        clue = self._normalize_clue_text(clue)
        if not clue:
            return None

        templates = {
            'remembering': [
                "The term described as {clue} is _______.",
                "The concept referred to by {clue} is _______.",
            ],
            'understanding': [
                "The concept best explained by {clue} is _______.",
                "The idea described by {clue} is _______.",
            ],
            'applying': [
                "In a situation involving {clue}, the relevant concept is _______.",
                "When applying ideas related to {clue}, the key concept is _______.",
            ],
            'analyzing': [
                "When analyzing a case involving {clue}, the key concept is _______.",
                "For examining a situation involving {clue}, the central concept is _______.",
            ],
            'evaluating': [
                "When judging a case involving {clue}, the concept to consider is _______.",
                "For evaluating a situation involving {clue}, the relevant concept is _______.",
            ],
            'creating': [
                "When designing a response to {clue}, the guiding concept is _______.",
                "For creating a solution related to {clue}, the key concept is _______.",
            ],
        }
        choices = templates.get(bloom_level, templates['remembering'])
        return random.choice(choices).format(clue=clue)

    def _build_true_false_statement_from_clue(self, keyword, clue):
        """Create a declarative statement from a keyword/clue pair."""
        clue = self._normalize_clue_text(clue)
        keyword = str(keyword or '').strip()
        if not keyword or not clue:
            return None

        templates = [
            "{keyword} refers to {clue}.",
            "{keyword} is best described as {clue}.",
            "The term {keyword} is used for {clue}.",
        ]
        return random.choice(templates).format(keyword=keyword, clue=clue)

    def _build_identification_stem_from_clue(self, clue, bloom_level):
        """Build an identification stem from a clue without exposing the answer."""
        clue = self._normalize_clue_text(clue)
        if not clue:
            return None

        templates = {
            'remembering': [
                "Identify the term described by {clue}.",
                "What term matches this description: {clue}?",
            ],
            'understanding': [
                "What concept is best explained by {clue}?",
                "Identify the idea described in this explanation: {clue}.",
            ],
            'applying': [
                "In a situation involving {clue}, what concept should be identified?",
                "What term is most relevant to a case involving {clue}?",
            ],
            'analyzing': [
                "When analyzing a case involving {clue}, what concept is central?",
                "Identify the concept most relevant to examining {clue}.",
            ],
            'evaluating': [
                "When judging a case involving {clue}, what concept should be identified?",
                "What term is most important when evaluating {clue}?",
            ],
            'creating': [
                "When designing a response to {clue}, what concept should guide it?",
                "Identify the key concept needed to create a solution for {clue}.",
            ],
        }
        choices = templates.get(bloom_level, templates['remembering'])
        return random.choice(choices).format(clue=clue)

    def _rewrite_copied_objective_stem(self, question, text_content):
        """Attempt to rewrite copied objective stems into clue-based variants."""
        q_type = str(question.get('question_type') or '').strip()
        if q_type not in {'multiple_choice', 'fill_in_blank', 'identification'}:
            return None

        answer = str(question.get('correct_answer') or '').strip()
        if not answer:
            return None

        bloom_level = question.get('bloom_level') or 'remembering'
        clue = self._extract_question_clue(text_content, answer)
        if not clue:
            return None

        if q_type == 'multiple_choice':
            rewritten = self._build_mcq_stem_from_clue(clue, bloom_level)
        elif q_type == 'fill_in_blank':
            rewritten = self._build_fill_in_blank_stem_from_clue(clue, bloom_level)
        else:
            rewritten = self._build_identification_stem_from_clue(clue, bloom_level)

        rewritten = self._sanitize_generated_text(rewritten)
        if not rewritten:
            return None
        if self._question_looks_copied_from_source(rewritten, text_content):
            return None
        if len(answer) >= 4 and re.search(re.escape(answer), rewritten, flags=re.IGNORECASE):
            return None
        return rewritten

    @staticmethod
    def _normalize_for_copy_check(text):
        """Normalize text so copied-source detection ignores wrappers and punctuation."""
        text = str(text or '')
        text = re.sub(r'_{3,}', ' ', text)
        text = text.strip().lower()
        prefix_patterns = [
            r'^(?:true\s+or\s+false\s*:?\s*)',
            r'^(?:state\s+whether\s+the\s+(?:following\s+)?statement\s+is\s+(?:true\s+or\s+false|accurate)\s*:?\s*)',
            r'^(?:determine\s+(?:if|whether)\s+the\s+statement\s+is\s+(?:correct|accurate)\s*:?\s*)',
            r'^(?:evaluate\s+the\s+accuracy\s+of\s+this\s+statement\s*:?\s*)',
            r'^(?:judge\s+the\s+accuracy\s+of\s+this\s+statement\s*:?\s*)',
            r'^(?:fill\s+in\s+the\s+blank\s*:?\s*)',
            r'^(?:complete\s+the\s+statement\s*:?\s*)',
            r'^(?:supply\s+the\s+missing\s+(?:word|term)\s*:?\s*)',
            r'^(?:provide\s+the\s+correct\s+term\s*:?\s*)',
            r'^(?:write\s+the\s+missing\s+word\s*:?\s*)',
            r'^(?:what\s+word\s+completes\s+the\s+sentence\??\s*)',
            r'^(?:give\s+the\s+missing\s+term\s*:?\s*)',
        ]
        for pattern in prefix_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _question_looks_copied_from_source(self, question_text, source_text):
        """Reject objective stems that are effectively copied from a module sentence."""
        q_norm = self._normalize_for_copy_check(self._sanitize_generated_text(question_text))
        if len(q_norm.split()) < 6:
            return False

        source_clean = self._clean_text_for_questions(source_text)
        for sentence in self._sent_tokenize(source_clean):
            s_norm = self._normalize_for_copy_check(sentence)
            if len(s_norm.split()) < 6:
                continue
            if q_norm == s_norm:
                return True

            ratio = SequenceMatcher(None, q_norm, s_norm).ratio()
            # Allow some amount of shared wording: only reject when the similarity is extremely high.
            # This reduces false positives when our template-based stems are close to source text.
            if ratio >= 0.985:  # raised threshold to allow more legitimate paraphrases
                return True

            q_words = set(q_norm.split())
            s_words = set(s_norm.split())
            overlap = len(q_words & s_words) / max(min(len(q_words), len(s_words)), 1)
            if overlap >= 0.98 and abs(len(q_words) - len(s_words)) <= 4:
                return True

        return False
    
    def _distribute_questions_by_type_and_difficulty(self, module_content, exam_config):
        """Generate questions using improved local methods"""
        try:
            logger.info("=" * 80)
            logger.info("QUESTION GENERATION START")
            logger.info("=" * 80)
            
            question_types_details = exam_config.get('question_types_details')
            
            if not question_types_details:
                logger.warning("❌ No question_types_details")
                return None
            
            text_content = self._extract_text_content(module_content)
            text_content = self._clean_text_for_questions(text_content)
            logger.info(f"📄 Content length: {len(text_content)} characters")

            # Module IDs passed from the service so problem_solving can pull from DB
            module_ids = exam_config.get('module_ids', [])

            all_questions = []
            # Track how many were generated vs requested per type for the top-up pass
            type_actual = {}   # qt_config index → actual generated count
            type_target = {}   # qt_config index → requested count

            for idx, qt_config in enumerate(question_types_details):
                logger.info("-" * 80)
                logger.info(f"Config #{idx + 1}/{len(question_types_details)}")

                question_type = qt_config['type']
                total_count = qt_config['count']
                points = qt_config['points']
                difficulty_dist = qt_config['difficulty_distribution']
                bloom_level = qt_config.get('bloom_level', None)

                logger.info(f"  Type: {question_type}")
                logger.info(f"  Target: {total_count} questions")
                logger.info(f"  Points: {points} each")
                logger.info(f"  Bloom level: {bloom_level or 'auto (by difficulty)'}")

                type_target[idx] = total_count
                generated_for_type = 0

                for difficulty, count in difficulty_dist.items():
                    if count == 0:
                        continue

                    logger.info(f"    🎯 Need: {count} {difficulty} {question_type}")

                    questions = self._generate_questions_by_type(
                        text_content=text_content,
                        question_type=question_type,
                        difficulty=difficulty,
                        count=count,
                        points=points,
                        bloom_level=bloom_level,
                        module_ids=module_ids,
                    )

                    logger.info(f"    ✅ Got: {len(questions)}/{count}")
                    all_questions.extend(questions)
                    generated_for_type += len(questions)

                type_actual[idx] = generated_for_type

            logger.info("=" * 80)
            logger.info(f"TOTAL: {len(all_questions)} questions")
            logger.info("=" * 80)

            # ── Type-locked top-up pass ────────────────────────────────────────
            # Retry only the SAME question type that is short. Never substitute
            # missing slots with a different type.
            target_count = exam_config.get('num_questions', len(all_questions))
            shortfall = target_count - len(all_questions)

            if shortfall > 0:
                logger.warning(
                    f"⚠️  First pass generated {len(all_questions)}/{target_count} — "
                    f"running type-locked top-up for {shortfall} missing questions"
                )
                short_configs = [
                    (i, qt_config)
                    for i, qt_config in enumerate(question_types_details)
                    if type_actual.get(i, 0) < type_target.get(i, 0)
                ]

                for i, qt_config in short_configs:
                    per_type_needed = type_target.get(i, 0) - type_actual.get(i, 0)
                    if per_type_needed <= 0:
                        continue

                    qt_type = qt_config['type']
                    qt_pts = qt_config['points']
                    bl = qt_config.get('bloom_level', None)
                    diff_dist = qt_config.get('difficulty_distribution', {}) or {}

                    # Try configured difficulties first (largest share first), then
                    # remaining standard levels to maximize same-type fill.
                    ordered_difficulties = [
                        d for d, c in sorted(diff_dist.items(), key=lambda item: item[1], reverse=True)
                        if c > 0
                    ]
                    for d in ('easy', 'medium', 'hard'):
                        if d not in ordered_difficulties:
                            ordered_difficulties.append(d)

                    for diff in ordered_difficulties:
                        if per_type_needed <= 0:
                            break

                        extra = self._generate_questions_by_type(
                            text_content=text_content,
                            question_type=qt_type,
                            difficulty=diff,
                            count=per_type_needed,
                            points=qt_pts,
                            bloom_level=bl,
                            module_ids=module_ids,
                        )
                        gained = len(extra) if extra else 0
                        if gained <= 0:
                            continue

                        all_questions.extend(extra)
                        type_actual[i] = type_actual.get(i, 0) + gained
                        per_type_needed -= gained
                        logger.info(
                            f"  🔄 Type-locked top-up: +{gained} {qt_type} "
                            f"(difficulty={diff}, remaining for type={per_type_needed})"
                        )

                    if per_type_needed > 0:
                        logger.warning(
                            f"  ⚠️  Type '{qt_type}' still short by {per_type_needed} "
                            f"after same-type fallback attempts."
                        )

                remaining = target_count - len(all_questions)
                if remaining > 0:
                    logger.warning(
                        f"⚠️  Type-locked top-up complete — still {remaining} short. "
                        f"Module content is insufficient for the requested question count."
                    )
                else:
                    logger.info("✅ Type-locked top-up successful — target count reached.")

            # ── FINAL CLEANUP: catch any remaining char-per-line / squished artifacts ──
            cleaned_questions = []
            for q in all_questions:
                qt = q.get('question_text', '')
                qt = self._sanitize_generated_text(qt)
                # Reject questions with remaining squished text > 25 alpha chars
                if self._has_text_artifact(qt):
                    logger.warning(f"  🗑️  Dropping question with squished artifact: {qt[:60]}...")
                    continue
                q['question_text'] = qt
                # Also clean correct_answer
                ans = q.get('correct_answer', '')
                if ans and ans not in ('True', 'False'):
                    ans = self._sanitize_generated_text(ans)
                    q['correct_answer'] = ans
                # Also clean MCQ options
                opts = q.get('options')
                if opts and isinstance(opts, list):
                    q['options'] = [self._sanitize_generated_text(o) if isinstance(o, str) else o for o in opts]
                cleaned_questions.append(q)

            if len(cleaned_questions) < len(all_questions):
                logger.info(
                    f"  🧹 Final cleanup dropped {len(all_questions) - len(cleaned_questions)} "
                    f"questions with text artifacts"
                )

            return cleaned_questions

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    # Enforced mapping: which Bloom's levels are valid per difficulty
    BLOOM_MAP = {
        'easy':   ['remembering', 'understanding', 'applying'],
        'medium': ['applying', 'analyzing'],
        'hard':   ['analyzing', 'evaluating', 'creating'],
    }

    COGNITIVE_LEVELS = (
        'remembering', 'understanding', 'applying',
        'analyzing', 'evaluating', 'creating'
    )

    DEFAULT_COGNITIVE_DISTRIBUTION = {
        'remembering': 0.30,
        'understanding': 0.20,
        'applying': 0.20,
        'analyzing': 0.10,
        'evaluating': 0.10,
        'creating': 0.10,
    }

    # Centralized question stems by Bloom level (use “___” as the slot)
    BLOOM_STEMS = {
        'remembering': [
            "Which of the following best describes ___?",
            "What is the definition of ___?",
            "Which term refers to ___?",
            "What does ___ stand for?",
            "Which statement correctly defines ___?",
            "What is the primary purpose of ___?",
            "Which option identifies ___?",
            "What is meant by ___?",
            "Which concept represents ___?",
            "What is the function of ___?",
            "Which of the following is an example of ___?",
            "What is the standard definition of ___?",
            "Which component is responsible for ___?",
            "What does the term ___ indicate?",
            "Which description accurately matches ___?",
            "What is the role of ___?",
            "Which element defines ___?",
            "What is the name given to ___?",
            "Which option correctly labels ___?",
            "What is the basic characteristic of ___?"
        ],
        'understanding': [
            "Which statement best explains ___?",
            "Why is ___ important?",
            "What is the main idea behind ___?",
            "Which explanation best describes how ___ works?",
            "What is the relationship between ___ and ___?",
            "Which statement clarifies the purpose of ___?",
            "What distinguishes ___ from ___?",
            "How does ___ contribute to ___?",
            "Which of the following illustrates ___?",
            "What is the underlying principle of ___?",
            "Which statement summarizes ___?",
            "What condition leads to ___?",
            "Why does ___ occur?",
            "Which option demonstrates understanding of ___?",
            "How can ___ be interpreted?",
            "What effect does ___ have on ___?",
            "Which explanation best accounts for ___?",
            "What is implied when ___ occurs?",
            "Which statement reflects the concept of ___?",
            "How does ___ influence ___?"
        ],
        'applying': [
            "In the following scenario, which action should be taken?",
            "How would ___ be applied in this situation?",
            "Which method would correctly implement ___?",
            "What would happen if ___ is configured this way?",
            "Which configuration ensures ___?",
            "How should ___ be used to achieve ___?",
            "Which step is necessary when applying ___?",
            "What is the correct procedure for ___?",
            "Which option demonstrates proper use of ___?",
            "How would you apply ___ to solve ___?",
            "In practice, which approach would achieve ___?",
            "Which solution correctly addresses ___?",
            "What is the most appropriate tool for ___?",
            "Which command would execute ___?",
            "How should ___ be adjusted under ___ conditions?",
            "What is the correct response when ___ occurs?",
            "Which technique would you use to implement ___?",
            "What would be the result of applying ___?",
            "Which scenario requires the use of ___?",
            "How can ___ be used to improve ___?"
        ],
        'analyzing': [
            "Which factor most directly affects ___?",
            "What is the key difference between ___ and ___?",
            "Which component has the greatest impact on ___?",
            "What is the most significant cause of ___?",
            "Which pattern can be observed in ___?",
            "What distinguishes the structure of ___?",
            "Which relationship exists between ___ and ___?",
            "What would most likely result from ___?",
            "Which element is critical for ___?",
            "What is the logical consequence of ___?",
            "Which scenario best demonstrates ___?",
            "What structural feature defines ___?",
            "Which assumption underlies ___?",
            "Which variable most influences ___?",
            "What evidence supports ___?",
            "Which option reveals a flaw in ___?",
            "What dependency exists in ___?",
            "Which sequence correctly represents ___?",
            "What comparison highlights the difference in ___?",
            "Which element determines the outcome of ___?"
        ],
        'evaluating': [
            "Which approach is most appropriate for ___?",
            "Which option provides the best solution to ___?",
            "What is the most efficient method for ___?",
            "Which strategy yields the optimal result for ___?",
            "Which statement is most accurate regarding ___?",
            "What is the strongest justification for ___?",
            "Which decision would produce the most reliable outcome?",
            "What is the most suitable configuration for ___?",
            "Which argument best supports ___?",
            "Which method minimizes risk in ___?",
            "Which solution offers the greatest scalability?",
            "What is the most secure approach to ___?",
            "Which design choice is most effective for ___?",
            "Which option would you recommend for ___?",
            "What is the most defensible conclusion about ___?",
            "Which assessment best evaluates ___?",
            "Which policy would best regulate ___?",
            "What is the most practical implementation of ___?",
            "Which choice aligns best with ___ objectives?",
            "Which conclusion is most logically supported by ___?"
        ]
    }

    # ──────────────────────────────────────────────────────────────────────
    # MATH MODE constants
    # ──────────────────────────────────────────────────────────────────────
    _MATH_MODE_THRESHOLD = 0.03  # min ratio of math-indicator chars to total text

    _MATH_INDICATOR_RE = re.compile(
        r'[=<>≤≥±∓∑∏∫√π∞≠≈∀∃∂∇∈∉⊂⊃∪∩×÷'
        r'αβγδεζηθικλμνξρστυφχψωΩΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨ]'
        r'|\b(?:sin|cos|tan|cot|log|ln|exp|lim|sqrt)\b'
        r'|\^[0-9]'
        r'|\[EQUATION:'
    )

    _MATH_ANALYSIS_TEMPLATES = [
        "Explain why the formula for {concept} is defined the way it is.",
        "Compare {concept} with another related formula or method.",
        "What are the conditions under which {concept} is valid or applicable?",
        "Analyze the relationship between the variables in: {equation}.",
        "How does changing {variable} affect the result of {equation}?",
        "Describe a real-world application of {concept}.",
        "What assumptions are made when applying {concept}?",
        "Why is each variable in the expression {equation} necessary?",
    ]

    _MATH_MUTATION_OPS = {
        '+': '-', '-': '+', '*': '/', '/': '*',
        '^2': '^3', '^3': '^2', '²': '³', '³': '²',
    }

    def _resolve_bloom_level(self, bloom_level, difficulty):
        """Resolve bloom level.

        - Explicit valid levels are preserved.
        - 'auto'/'random'/empty values trigger random selection from allowed levels
          for the current difficulty.
        """
        allowed = self.BLOOM_MAP.get(difficulty, ['remembering'])
        if not allowed:
            allowed = ['remembering']

        normalized = (str(bloom_level).strip().lower().replace(' ', '_')
                      if bloom_level is not None else '')
        if normalized in ('', 'auto', 'random', 'none', 'null'):
            return random.choice(allowed)

        valid_levels = {
            'remembering', 'understanding', 'applying',
            'analyzing', 'evaluating', 'creating', 'problem_solving'
        }
        if normalized in valid_levels:
            return normalized

        return random.choice(allowed)

    def _auto_classify_bloom_levels(self, questions):
        """Classify Bloom level from question text and overwrite question bloom_level."""
        if not questions:
            return questions
        try:
            if not hasattr(self, '_bloom_classifier') or self._bloom_classifier is None:
                from app.exam.bloom_classifier import BloomClassifier
                self._bloom_classifier = BloomClassifier()
            for question in questions:
                question_text = question.get('question_text', '')
                question['bloom_level'] = self._bloom_classifier.classify_question(question_text)
        except Exception as e:
            logger.warning(f"        ⚠️  Auto Bloom classification failed: {e}")
        return questions

    def _randomize_bloom_levels(self, questions, fallback_difficulty=None):
        """Assign random Bloom levels per question using difficulty-aware pools."""
        if not questions:
            return questions
        for question in questions:
            difficulty = question.get('difficulty_level') or fallback_difficulty
            allowed = self.BLOOM_MAP.get(difficulty, ['remembering']) or ['remembering']
            question['bloom_level'] = random.choice(allowed)
        return questions

    def _normalize_cognitive_distribution(self, target_distribution):
        """Normalize cognitive distribution into ratios that sum to 1.0."""
        if isinstance(target_distribution, dict) and target_distribution:
            source = target_distribution
        else:
            source = self.DEFAULT_COGNITIVE_DISTRIBUTION

        normalized = {}
        for level in self.COGNITIVE_LEVELS:
            raw_value = source.get(level, 0)
            try:
                value = float(raw_value)
            except Exception:
                value = 0.0
            normalized[level] = max(value, 0.0)

        total_raw = sum(normalized.values())
        if total_raw <= 0:
            normalized = dict(self.DEFAULT_COGNITIVE_DISTRIBUTION)
            total_raw = sum(normalized.values())

        # Accept either ratio input (0..1) or percent input (0..100).
        if total_raw > 1.5:
            normalized = {level: value / 100.0 for level, value in normalized.items()}

        ratio_total = sum(normalized.values())
        if ratio_total <= 0:
            return dict(self.DEFAULT_COGNITIVE_DISTRIBUTION)

        return {level: value / ratio_total for level, value in normalized.items()}

    @staticmethod
    def _ratios_to_counts(total_questions, ratios):
        """Convert ratios to integer counts with largest-remainder balancing."""
        if total_questions <= 0:
            return {level: 0 for level in ratios}

        raw = {level: ratios[level] * total_questions for level in ratios}
        counts = {level: int(raw[level]) for level in ratios}
        remaining = total_questions - sum(counts.values())

        if remaining > 0:
            by_remainder = sorted(
                ratios.keys(),
                key=lambda level: raw[level] - counts[level],
                reverse=True
            )
            idx = 0
            while remaining > 0 and by_remainder:
                level = by_remainder[idx % len(by_remainder)]
                counts[level] += 1
                remaining -= 1
                idx += 1

        return counts

    def _apply_target_bloom_distribution(self, questions, target_distribution=None):
        """Reassign Bloom levels to match target cognitive distribution as closely as possible."""
        if not questions:
            return questions

        ratios = self._normalize_cognitive_distribution(target_distribution)
        target_counts = self._ratios_to_counts(len(questions), ratios)
        assigned_counts = {level: 0 for level in self.COGNITIVE_LEVELS}

        allowed_by_index = []
        for question in questions:
            difficulty = str(question.get('difficulty_level') or 'medium').lower()
            allowed = [
                level for level in (self.BLOOM_MAP.get(difficulty) or ['remembering'])
                if level in self.COGNITIVE_LEVELS
            ]
            if not allowed:
                allowed = ['remembering']
            allowed_by_index.append(allowed)

        eligible_counts = {
            level: sum(1 for allowed in allowed_by_index if level in allowed)
            for level in self.COGNITIVE_LEVELS
        }
        # Allocate scarce levels first to improve match quality.
        allocation_order = sorted(
            self.COGNITIVE_LEVELS,
            key=lambda level: (eligible_counts[level], -target_counts[level])
        )

        assignments = [None] * len(questions)
        unassigned = set(range(len(questions)))

        for level in allocation_order:
            needed = target_counts[level] - assigned_counts[level]
            if needed <= 0:
                continue

            candidates = [idx for idx in unassigned if level in allowed_by_index[idx]]
            if not candidates:
                continue

            random.shuffle(candidates)
            take = min(needed, len(candidates))
            for idx in candidates[:take]:
                assignments[idx] = level
                assigned_counts[level] += 1
                unassigned.remove(idx)

        # Fill remaining questions with the allowed level that has largest shortfall.
        for idx in list(unassigned):
            allowed = allowed_by_index[idx]
            best_level = max(
                allowed,
                key=lambda level: target_counts[level] - assigned_counts[level]
            )
            if target_counts[best_level] - assigned_counts[best_level] <= 0:
                best_level = min(allowed, key=lambda level: assigned_counts[level])

            assignments[idx] = best_level
            assigned_counts[best_level] += 1

        for idx, question in enumerate(questions):
            question['bloom_level'] = assignments[idx] or 'remembering'

        deviations = {
            level: assigned_counts[level] - target_counts[level]
            for level in self.COGNITIVE_LEVELS
            if assigned_counts[level] != target_counts[level]
        }
        if deviations:
            logger.info(
                "Applied Bloom target with difficulty constraints. "
                f"Target={target_counts}, actual={assigned_counts}, deviations={deviations}"
            )
        else:
            logger.info(f"Applied Bloom target exactly: {assigned_counts}")

        return questions

    def _pick_bloom_stem(self, bloom_level: str):
        stems = self.BLOOM_STEMS.get(bloom_level, self.BLOOM_STEMS.get('remembering', []))
        if not stems:
            return "What best fits ___?"
        return random.choice(stems)

    def _query_module_questions(self, module_ids, mq_type, difficulty, limit, target_type=None, points=None):
        """
        DB-first helper: fetch pre-processed ModuleQuestion records for the given
        type and difficulty.  Returns formatted question dicts with
        _module_question_id and _image_id set so ExamQuestion.module_question_id
        is populated by ExamService.

        Falls back to any difficulty when the exact-difficulty pool is empty.
        """
        if not module_ids:
            return []
        try:
            from app.module_processor.models import ModuleQuestion as MQ
            from app.module_processor.saved_module import SavedModuleService
            # Build type filter — None means "all types", str = exact match, list = .in_()
            def _type_filter(q):
                if mq_type is None:
                    return q
                if isinstance(mq_type, (list, tuple)):
                    return q.filter(MQ.question_type.in_(mq_type))
                return q.filter(MQ.question_type == mq_type)

            def _diff_filter(q):
                if difficulty is None:
                    return q
                return q.filter(MQ.difficulty_level == difficulty)

            base_q = _type_filter(MQ.query.filter(MQ.module_id.in_(module_ids)))
            qs = (
                _diff_filter(base_q)
                .order_by(MQ.created_at.desc())
                .limit(limit * 4)
                .all()
            )
            # Supplement with other difficulties only when the actual count needed
            # (limit // 4) cannot be met — callers pass count * 4 as limit so
            # comparing raw len(qs) < limit would always trigger for MCQ (42 easy
            # records < 80 limit) and steal medium records from T/F / FIB pools.
            _need = limit // 4
            if difficulty is not None and len(qs) < _need:
                seen_ids = {mq.question_id for mq in qs}
                extra = (
                    base_q
                    .filter(MQ.question_id.notin_(seen_ids))
                    .order_by(MQ.created_at.desc())
                    .limit((_need - len(qs)) * 4)
                    .all()
                )
                qs = qs + extra
            if self._module_question_targets:
                buckets = {}
                for mq in qs:
                    buckets.setdefault(mq.module_id, []).append(mq)

                for module_bucket in buckets.values():
                    random.shuffle(module_bucket)

                ordered_qs = []
                total_available = sum(len(module_bucket) for module_bucket in buckets.values())
                while len(ordered_qs) < total_available:
                    available_module_ids = [mid for mid in module_ids if buckets.get(mid)]
                    if not available_module_ids:
                        break

                    prioritized_module_ids = [
                        mid for mid in available_module_ids
                        if (self._module_question_targets.get(mid, 0) - self._module_question_usage.get(mid, 0)) > 0
                    ]
                    cycle_ids = prioritized_module_ids if prioritized_module_ids else available_module_ids
                    cycle_ids = sorted(
                        cycle_ids,
                        key=lambda mid: (
                            self._module_question_targets.get(mid, 0) - self._module_question_usage.get(mid, 0),
                            len(buckets.get(mid, []))
                        ),
                        reverse=True
                    )

                    progressed = False
                    for mid in cycle_ids:
                        module_bucket = buckets.get(mid, [])
                        if module_bucket:
                            ordered_qs.append(module_bucket.pop())
                            progressed = True

                    if not progressed:
                        break

                qs = ordered_qs
            else:
                random.shuffle(qs)
            results = []
            seen_in_call = set()  # local dedup — do NOT write to self.generated_questions here;
                                  # downstream _add_question_if_valid handles cross-generator tracking
            for mq in qs:
                if len(results) >= limit:
                    break
                # Reuse module-processor usability rules so legacy extracted rows
                # are filtered consistently during DB-first exam generation.
                usable, _reasons = SavedModuleService.is_question_usable_for_generation(
                    question_text=mq.question_text,
                    question_type=mq.question_type,
                    correct_answer=mq.correct_answer
                )
                if not usable:
                    continue
                # Skip DB questions with no usable correct answer
                if not mq.correct_answer or not mq.correct_answer.strip():
                    continue
                norm = self._normalize_text(mq.question_text)
                # Skip questions already accepted by a previous generator or this call
                if norm in self.generated_questions or norm in seen_in_call:
                    continue
                seen_in_call.add(norm)
                qt_lower = (mq.question_text or '').lower()
                ans_lower = (mq.correct_answer or '').lower()
                # Skip low-quality stems or leakage
                if "complete the sentence" in qt_lower or "what term completes" in qt_lower:
                    continue
                if ans_lower and len(ans_lower.strip()) > 3 and ans_lower in qt_lower:
                    continue
                if len(qt_lower.strip()) < 12:
                    continue
                # Skip char-per-line or squished DB text artifacts
                _q_lines = mq.question_text.splitlines()
                if len(_q_lines) > 3:
                    _single = sum(1 for _l in _q_lines if len(_l.strip()) <= 1)
                    if _single / len(_q_lines) > 0.4:
                        continue
                # Clean any residual char-per-line formatting in both text and answer
                _clean_qt = self._fix_spaced_characters(mq.question_text)
                _clean_qt = ExamGenerator._desquish_long_tokens(_clean_qt)
                _clean_ans = self._fix_spaced_characters(mq.correct_answer) if mq.correct_answer else mq.correct_answer
                # Reject if question text still contains squished artifacts after fix
                if any(len(w.rstrip(".,;:!?'\"")) > 25 and w.rstrip(".,;:!?'\"").isalpha() for w in (_clean_qt or '').split()):
                    continue
                results.append({
                    '_module_question_id': mq.question_id,
                    '_module_id':          mq.module_id,
                    '_image_id':           mq.image_id,
                    'question_text':       _clean_qt,
                    'correct_answer':      _clean_ans,
                    'question_type':       target_type if target_type else mq.question_type,
                    'difficulty_level':    mq.difficulty_level or difficulty,
                    'bloom_level':         self._resolve_bloom_level(None, mq.difficulty_level or difficulty),
                    'topic':               mq.topic or 'General',
                    'options':             None,
                    'points':              points if points is not None else 1,
                })
                if self._module_question_targets:
                    self._module_question_usage[mq.module_id] = self._module_question_usage.get(mq.module_id, 0) + 1
            _type_label = 'all' if mq_type is None else (
                ','.join(mq_type) if isinstance(mq_type, (list, tuple)) else mq_type
            )
            logger.info(
                f"        🗄️  DB pulled {len(results)}/{limit} [{_type_label}] questions "
                f"from modules {module_ids}"
            )
            return results
        except Exception as e:
            logger.warning(f"        ⚠️  DB-first query failed ({mq_type}): {e}")
            return []

    def _generate_questions_by_type(self, text_content, question_type, difficulty, count, points,
                                     bloom_level=None, module_ids=None):
        """Generate questions by type, respecting the teacher-selected Bloom's level.

        Special rule: if the teacher selected 'Problem Solving' as the Bloom's level
        (available for medium and hard difficulties), skip the normal type dispatcher
        and always generate computation / problem-solving questions.  This works for
        ANY base question type (identification, multiple_choice, etc.).

        module_ids is passed through from the exam_config so _generate_problem_solving
        can pull pre-processed questions from the module_questions DB table first.
        """
        normalized_bloom = (
            bloom_level.strip().lower().replace(' ', '_')
            if isinstance(bloom_level, str) else ''
        )
        auto_bloom = normalized_bloom == 'auto'
        random_bloom = normalized_bloom in ('', 'random', 'none', 'null')

        # Problem-solving bloom level only applies to identification and problem_solving types.
        # MCQ, True/False, and Fill-in-blank always generate their own question format
        # regardless of bloom level — even at hard difficulty.
        PS_ELIGIBLE_TYPES = {'identification', 'problem_solving'}
        if bloom_level == 'problem_solving' and question_type in PS_ELIGIBLE_TYPES:
            logger.info(f"        🧮 bloom_level=problem_solving → routing to _generate_problem_solving")
            ps_questions = self._generate_problem_solving(text_content, difficulty, count, points,
                                                          module_ids=module_ids)
            if len(ps_questions) >= count:
                return ps_questions
            # Not enough computation questions (e.g. no equations in module) — fall back to
            # the base question type so the exam is not left short.
            remaining = count - len(ps_questions)
            logger.info(
                f"        ⚠️  Only {len(ps_questions)}/{count} problem-solving questions found; "
                f"falling back to '{question_type}' for remaining {remaining}"
            )
            resolved_bloom = self._resolve_bloom_level(bloom_level, difficulty)
            fallback = self._dispatch_question_type(
                question_type, text_content, difficulty, remaining, points,
                resolved_bloom, module_ids
            )
            combined = ps_questions + fallback
            if auto_bloom:
                return self._auto_classify_bloom_levels(combined)
            if random_bloom:
                return self._randomize_bloom_levels(combined, difficulty)
            return combined

        resolved_bloom = self._resolve_bloom_level(None if auto_bloom else bloom_level, difficulty)
        try:
            generated = self._dispatch_question_type(
                question_type, text_content, difficulty, count, points,
                resolved_bloom, module_ids
            )
            if auto_bloom:
                return self._auto_classify_bloom_levels(generated)
            if random_bloom:
                return self._randomize_bloom_levels(generated, difficulty)
            return generated
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return []

    def _dispatch_question_type(self, question_type, text_content, difficulty, count,
                                points, resolved_bloom, module_ids=None):
        """Route to the correct question-type generator (with math mode intercept)."""
        # ── Math mode intercept ──────────────────────────────────────────
        if getattr(self, '_math_mode', False):
            math_result = self._dispatch_math_question_type(
                question_type, text_content, difficulty, count, points,
                resolved_bloom, module_ids
            )
            if len(math_result) >= count:
                return math_result
            # Partial result: fill remainder with standard generator
            if math_result:
                remaining = count - len(math_result)
                standard = self._dispatch_standard_question_type(
                    question_type, text_content, difficulty, remaining,
                    points, resolved_bloom, module_ids
                )
                return math_result + standard
            # Math generator produced nothing: fall through to standard

        return self._dispatch_standard_question_type(
            question_type, text_content, difficulty, count, points,
            resolved_bloom, module_ids
        )

    def _dispatch_math_question_type(self, question_type, text_content, difficulty,
                                      count, points, resolved_bloom, module_ids=None):
        """Route to math-specific generators when math mode is active."""
        if question_type == 'multiple_choice':
            return self._math_generate_mcq(text_content, difficulty, count, points, resolved_bloom, module_ids)
        elif question_type == 'true_false':
            return self._math_generate_true_false(text_content, difficulty, count, points, resolved_bloom, module_ids)
        elif question_type in ('fill_in_blank', 'factual'):
            return self._math_generate_fill_in_blank(text_content, difficulty, count, points, resolved_bloom, module_ids)
        elif question_type == 'identification':
            return self._math_generate_identification(text_content, difficulty, count, points, resolved_bloom, module_ids)
        elif question_type == 'analysis':
            return self._math_generate_analysis(text_content, difficulty, count, points, resolved_bloom, module_ids)
        # problem_solving + conceptual: already handled well by standard path
        return []

    def _dispatch_standard_question_type(self, question_type, text_content, difficulty, count,
                                          points, resolved_bloom, module_ids=None):
        """Standard (non-math) question-type router."""
        if question_type == 'multiple_choice':
            return self._generate_multiple_choice(text_content, difficulty, count, points, resolved_bloom, module_ids=module_ids)
        elif question_type == 'true_false':
            return self._generate_true_false(text_content, difficulty, count, points, resolved_bloom, module_ids=module_ids)
        elif question_type == 'fill_in_blank':
            return self._generate_fill_in_blank(text_content, difficulty, count, points, resolved_bloom,
                                                module_ids=module_ids)
        elif question_type == 'identification':
            return self._generate_identification(text_content, difficulty, count, points, resolved_bloom,
                                                 module_ids=module_ids)
        elif question_type == 'factual':
            # FIX: Factual questions — DB-first pull, then fill_in_blank as fallback
            questions = []
            remaining = count
            if module_ids:
                db_qs = self._query_module_questions(module_ids, 'factual', difficulty, count)
                if len(db_qs) >= count:
                    logger.info(f"        ✅ DB-first satisfied all {count} factual questions")
                    return db_qs
                questions.extend(db_qs)
                remaining = count - len(db_qs)
                logger.info(f"        ℹ️  DB returned {len(db_qs)} factual questions, generating {remaining} more via fill_in_blank fallback")
            if remaining > 0:
                fib = self._generate_fill_in_blank(
                    text_content, difficulty, remaining, points,
                    resolved_bloom, module_ids=module_ids
                )
                questions.extend(fib)
            logger.info(f"        ✅ Factual total: {len(questions)}/{count}")
            return questions
        elif question_type == 'conceptual':
            return self._generate_conceptual(text_content, difficulty, count, points, resolved_bloom,
                                             module_ids=module_ids)
        elif question_type == 'analysis':
            return self._generate_analysis(text_content, difficulty, count, points, resolved_bloom,
                                           module_ids=module_ids)
        elif question_type == 'problem_solving':
            return self._generate_problem_solving(text_content, difficulty, count, points,
                                                  module_ids=module_ids)
        else:
            logger.warning(f"        ⚠️  Unknown question type '{question_type}' — skipping")
            return []
    
    def _split_into_sections(self, text):
        """Split text into topic sections by heading detection or equal chunks."""
        heading_pattern = re.compile(
            r'(?:^|\n\n)([A-Z][^\n]{0,79})(?=\n\n)', re.MULTILINE
        )
        positions = [m.start() for m in heading_pattern.finditer(text)]

        if len(positions) >= 2:
            sections = []
            for i, pos in enumerate(positions):
                start = pos
                end = positions[i + 1] if i + 1 < len(positions) else len(text)
                chunk = text[start:end].strip()
                if len(chunk) > 100:
                    sections.append(chunk)
            if sections:
                return sections

        # Fallback: split into equal thirds
        chunk_size = max(len(text) // 3, 300)
        return [text[i:i + chunk_size].strip()
                for i in range(0, len(text), chunk_size)
                if text[i:i + chunk_size].strip()]

    def _proportional_keywords(self, text, top_n=50):
        """Extract keywords proportionally across document sections for topic coverage."""
        sections = self._split_into_sections(text)
        if len(sections) <= 1:
            return self.tfidf_engine.extract_keywords(text, top_n=top_n)

        per_section = max(8, top_n // len(sections))
        merged = []
        seen = set()
        for section in sections:
            try:
                self.tfidf_engine.add_document(section)
                sec_kw = self.tfidf_engine.extract_keywords(section, top_n=per_section)
                for kw, sc in sec_kw:
                    if kw.lower() not in seen:
                        merged.append((kw, sc))
                        seen.add(kw.lower())
            except Exception:
                continue
        # Fill remaining slots from full-text if sections didn't yield enough
        if len(merged) < top_n:
            full_kw = self.tfidf_engine.extract_keywords(text, top_n=top_n)
            for kw, sc in full_kw:
                if kw.lower() not in seen:
                    merged.append((kw, sc))
                    seen.add(kw.lower())
        return merged[:top_n]

    def _generate_multiple_choice(self, text_content, difficulty, count, points, bloom_level='remembering', module_ids=None):
        """
        Context-sentence MCQ generation.

        For every keyword the answer is the keyword itself; the question is formed
        by blanking the keyword in the sentence where it appears.  Other TF-IDF
        keywords from the document are used as distractors, so questions are:
        - Unique (each sentence is different)
        - Content-specific (based on real sentences, not generic templates)
        - Reliably achievable (distractors always available from keyword pool)

        DB-FIRST FALLBACK: When text-based generation yields 0 (e.g. math modules
        with formula-heavy content), uses stored factual Q&A pairs as MCQ stems and
        draws distractors from the pool of other correct answers.
        """
        logger.info(f"        📝 Generating {count} MCQ ({difficulty}, bloom={bloom_level})...")
        questions = []

        try:
            top_n = count * 25
            self.tfidf_engine.add_document(text_content)
            tfidf_keywords = self._proportional_keywords(text_content, top_n=top_n)
            if not tfidf_keywords:
                tfidf_keywords = []

            keywords = self._enhance_keyword_selection_with_nlp(text_content, tfidf_keywords)
            # Strip blank-fill artifacts (strings of underscores/dashes, answer markers)
            keywords = [
                (kw, sc) for kw, sc in keywords
                if not re.fullmatch(r'[_\-\s]+', kw)
                and not re.search(r'\(correct\s+answer\)', kw, re.IGNORECASE)
                and len(kw.strip()) > 1
            ]
            all_kw_words = [kw for kw, _ in keywords]

            # Clean text then split into valid question sentences
            clean_text_mcq = self._clean_text_for_questions(text_content)
            raw_sentences = [
                s for s in self._sent_tokenize(clean_text_mcq)
                if 20 < len(s) < 350
                and ExamGenerator._is_valid_question_sentence(s)
            ]

            # Shuffle keyword order for variety across calls
            shuffled_keywords = list(keywords)
            random.shuffle(shuffled_keywords)

            for keyword, score in shuffled_keywords:
                if len(questions) >= count:
                    break
                if self._is_low_quality_objective_answer(keyword, question_type='multiple_choice'):
                    continue

                clue = self._extract_question_clue(clean_text_mcq, keyword)
                question_text = self._build_mcq_stem_from_clue(clue, bloom_level) if clue else None

                if not question_text:
                    # Fallback only when no clue can be derived from the source text.
                    candidate_sentences = [
                        s for s in raw_sentences
                        if re.search(r'\b' + re.escape(keyword) + r'\b', s, re.IGNORECASE)
                    ]
                    if not candidate_sentences:
                        continue

                    sentence = random.choice(candidate_sentences)
                    blanked = re.sub(
                        r'\b' + re.escape(keyword) + r'\b',
                        '_______',
                        sentence,
                        count=1,
                        flags=re.IGNORECASE
                    ).strip()

                    if re.search(r'\b' + re.escape(keyword) + r'\b', blanked, re.IGNORECASE):
                        continue
                    if '_______' not in blanked:
                        continue
                    question_text = f"Which term best completes this statement: {blanked.rstrip('.')}?"

                # Distractors: other keywords ranked by semantic similarity to correct answer.
                # Filter out generic/short terms that make poor MCQ distractors.
                _DISTRACTOR_SKIP = frozenset({
                    'exam', 'data', 'bits', 'field', 'host', 'hosts', 'count', 'route',
                    'type', 'mode', 'node', 'link', 'unit', 'form', 'term', 'code', 'role',
                    'rate', 'base', 'case', 'item', 'list', 'name', 'part', 'step', 'time',
                    'area', 'cost', 'side', 'note', 'line', 'text', 'word', 'file', 'page',
                    'user', 'need', 'class', 'level', 'point', 'group', 'order', 'layer',
                    'hops', 'nic', 'mac', 'rip', 'tcp', 'udp', 'bit', 'net', 'lan', 'wan',
                    'ip', 'arp', 'size', 'port', 'flag', 'byte', 'bits', 'used', 'true',
                    'false', 'null', 'each', 'both', 'also', 'same', 'thus',
                })
                other_kw = [
                    kw for kw in all_kw_words
                    if kw.lower() != keyword.lower()
                    and len(kw) >= 4
                    and kw.lower() not in _DISTRACTOR_SKIP
                    and not self._is_too_generic_wordnet(kw.lower())
                ]
                if len(other_kw) >= 3:
                    try:
                        st = self._get_sentence_transformer()
                        if st:
                            # Single batch encode: index 0 = correct answer, 1..N = candidates
                            all_texts = [keyword] + other_kw
                            embeddings = st.encode(all_texts)
                            correct_emb = embeddings[0]
                            correct_norm = np.linalg.norm(correct_emb)
                            scored = []
                            for i, kw in enumerate(other_kw):
                                cand_emb = embeddings[i + 1]
                                denom = correct_norm * np.linalg.norm(cand_emb)
                                sim = float(np.dot(correct_emb, cand_emb) / denom) if denom > 0 else 0.0
                                scored.append((kw, sim))
                            # Sweet spot: similar enough to be plausible, not so close as to be identical.
                            # Raised floor from 0.20 → 0.30 so distractors are domain-related.
                            in_range = [kw for kw, sim in scored if 0.30 <= sim <= 0.75]
                            if len(in_range) >= 3:
                                distractors = in_range[:3]
                            else:
                                distractors = [kw for kw, _ in sorted(scored, key=lambda x: abs(x[1] - 0.45))][:3]
                        else:
                            distractors = random.sample(other_kw, 3)
                    except Exception:
                        distractors = random.sample(other_kw, 3)
                elif len(other_kw) >= 1:
                    # Pad with WordNet taxonomy + semantic variations if pool is small
                    distractors = list(other_kw)
                    # WordNet co-hyponyms / hyponyms — taxonomically related terms
                    wn_distractors = self._get_wordnet_distractors(keyword, count=3)
                    distractors += [d for d in wn_distractors if d.lower() != keyword.lower()
                                    and d.lower() not in {x.lower() for x in distractors}]
                    if len(distractors) < 3:
                        variations = self.nlp_engine._generate_semantic_variations(keyword, 'concept')
                        distractors += [v for v in variations if v.lower() != keyword.lower()]
                    distractors = distractors[:3]
                else:
                    # Try WordNet first, then fall back to NLP engine
                    distractors = self._get_wordnet_distractors(keyword, count=3)
                    if len(distractors) < 2:
                        distractors += self.nlp_engine._generate_semantic_variations(keyword, 'concept')[:3]
                    distractors = distractors[:3]

                if len(distractors) < 3:
                    continue

                options = [keyword] + distractors[:3]
                # Ensure 4 distinct options
                options = list(dict.fromkeys(options))  # deduplicate preserving order
                if len(options) != 4:
                    continue
                random.shuffle(options)

                standardized = {
                    'question_text': question_text,
                    'question_type': 'multiple_choice',
                    'difficulty_level': difficulty,
                    'options': options,
                    'correct_answer': keyword,
                    'points': points,
                    'bloom_level': bloom_level
                }

                if self._validate_mcq_options_semantic(standardized):
                    if self._add_question_if_valid(standardized):
                        questions.append(standardized)

            # ── DB-FIRST FALLBACK ──────────────────────────────────────────────
            # When text-based generation yields nothing (e.g. math modules where
            # every sentence is rejected by _is_valid_question_sentence), pull
            # stored Q&A pairs (all types) and turn them into MCQs.
            if len(questions) < count and module_ids:
                logger.info("        ℹ️  Text-based MCQ yielded 0 — using DB questions as MCQ stems")
                db_qs = self._query_module_questions(
                    module_ids, None, difficulty, count * 4, points=points
                )
                # Keep only questions with short, usable answers (≤8 words) —
                # prevents paragraph-length MCQ options from conceptual/analysis types
                db_qs = [
                    q for q in db_qs
                    if len((q.get('correct_answer') or '').split()) <= 8
                ]
                # Build a pool of correct answers to use as distractors.
                # Apply the same quality filter as the text-based path so we
                # don't end up with garbage 3-4 letter distractors.
                _DB_DISTRACTOR_SKIP = frozenset({
                    'exam', 'data', 'bits', 'field', 'host', 'hosts', 'count', 'route',
                    'type', 'mode', 'node', 'link', 'unit', 'form', 'term', 'code', 'role',
                    'rate', 'base', 'case', 'item', 'list', 'name', 'part', 'step', 'time',
                    'area', 'cost', 'side', 'note', 'line', 'text', 'word', 'file', 'page',
                    'user', 'need', 'class', 'level', 'point', 'group', 'order', 'layer',
                    'hops', 'nic', 'mac', 'rip', 'tcp', 'udp', 'bit', 'net', 'lan', 'wan',
                    'ip', 'arp', 'size', 'port', 'flag', 'byte', 'used', 'true',
                    'false', 'null', 'each', 'both', 'also', 'same', 'thus',
                    'ccna', 'ccnp', 'ccie',
                })
                all_answers = [
                    q.get('correct_answer', '').strip()
                    for q in db_qs
                    if q.get('correct_answer', '').strip()
                    and len(q.get('correct_answer', '').strip()) >= 4
                    and q.get('correct_answer', '').strip().lower() not in _DB_DISTRACTOR_SKIP
                ]
                for q in db_qs:
                    if len(questions) >= count:
                        break
                    qt = ExamGenerator._fix_spaced_characters(
                        (q.get('question_text') or '').strip()
                    )
                    ans = (q.get('correct_answer') or '').strip()
                    if not qt or not ans:
                        continue
                    if self._is_low_quality_objective_answer(ans, question_type='multiple_choice'):
                        continue
                    # Skip questions whose correct answer is a generic/short word
                    ans_lower = ans.lower()
                    if ans_lower in _DB_DISTRACTOR_SKIP or len(ans) < 4:
                        continue
                    # Skip answers that are single non-alpha tokens (e.g. "≤", "3")
                    if len(ans) <= 2 or (len(ans.split()) == 1 and not any(c.isalpha() for c in ans)):
                        continue
                    # Reject squished-text artifacts in question text
                    if any(len(w.rstrip(".,;:!?'\"")) > 25 and w.rstrip(".,;:!?'\"").isalpha() for w in qt.split()):
                        continue
                    # Build distractor list from other stored answers
                    distractors = [a for a in all_answers if a.lower() != ans_lower]
                    random.shuffle(distractors)
                    distractors = distractors[:3]
                    if len(distractors) < 3:
                        continue
                    options = list(dict.fromkeys([ans] + distractors))
                    if len(options) != 4:
                        continue
                    random.shuffle(options)
                    mcq = {
                        'question_text': qt,
                        'question_type': 'multiple_choice',
                        'difficulty_level': difficulty,
                        'options': options,
                        'correct_answer': ans,
                        'points': points,
                        'bloom_level': bloom_level,
                        '_module_question_id': q.get('_module_question_id'),
                        '_image_id': q.get('_image_id'),
                    }
                    if self._add_question_if_valid(mcq):
                        questions.append(mcq)

            logger.info(f"        ✅ Generated {len(questions)}/{count}")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error: {str(e)}")
            return []

    def _validate_mcq_options_semantic(self, question):
        """
        Validate MCQ options using semantic similarity.
        Batch-encodes all options in a single transformer call (fast path).
        Rejects distractors that are semantically identical to the correct answer (>0.95).
        """
        transformer = self._get_sentence_transformer()
        if not transformer:
            return True  # Skip validation if transformer not available

        try:
            options = question.get('options', [])
            correct_answer = question.get('correct_answer', '')

            if len(options) < 2:
                return False

            distractors = [o for o in options if o != correct_answer]
            if not distractors:
                return True

            # Single batch encode — O(1) transformer calls regardless of option count
            all_texts = [correct_answer] + distractors
            embeddings = transformer.encode(all_texts, batch_size=len(all_texts), show_progress_bar=False)

            correct_emb = embeddings[0]
            correct_norm = np.linalg.norm(correct_emb)

            for i, distractor in enumerate(distractors, 1):
                if i >= len(embeddings):
                    break
                dist_norm = np.linalg.norm(embeddings[i])
                if correct_norm == 0 or dist_norm == 0:
                    continue
                similarity = float(np.dot(correct_emb, embeddings[i]) / (correct_norm * dist_norm))
                if similarity > 0.95:  # Raised from 0.9 — only reject near-identical distractors
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ Error validating MCQ options: {e}")
            return True  # Don't reject on error
    
    def _generate_true_false(self, text_content, difficulty, count, points, bloom_level='remembering', module_ids=None):
        """
        IMPROVED: Generate True/False with mix.
        DB-FIRST: When text sentences are insufficient, fall back to stored factual
        questions — reconstructing True statements by filling in the blank.
        """
        logger.info(f"        📝 Generating {count} T/F ({difficulty}, bloom={bloom_level})...")
        questions = []

        try:
            # Clean text first
            clean_text = self._clean_text_for_questions(text_content)

            sentences = [
                ExamGenerator._desquish_long_tokens(s) + ('.' if not s.endswith('.') else '')
                for s in self._sent_tokenize(clean_text)
                if 20 < len(s) < 350
                and len(s.split()) >= 3  # skip squashed/no-space artifacts
                and ExamGenerator._is_valid_question_sentence(s)
            ]

            if not sentences:
                # ── DB-first fallback: reconstruct True statements from stored
                # factual questions by filling the blank with the correct answer.
                if module_ids:
                    logger.info(
                        "        ℹ️  No valid text sentences — using DB questions for T/F"
                    )
                    db_qs = self._query_module_questions(
                        module_ids, None, difficulty, count * 4, points=points
                    )
                    # Exclude template-prompt questions — they produce terrible T/F statements
                    # e.g. "Explain the main concept..." → False: "does not explain the main concept..."
                    _TF_SKIP = re.compile(
                        r'^(Explain|Evaluate|Compute|Calculate|Compare|Critically|Analyze|'
                        r'Describe|Consider|Assess|Find|Determine|Show|Given|Formulate|'
                        r'Identify|What conclusions|What can be drawn)',
                        re.IGNORECASE
                    )
                    db_qs = [q for q in db_qs if not _TF_SKIP.match(q.get('question_text', '').strip())]
                    true_budget  = (count + 1) // 2
                    false_budget = count // 2
                    true_used = false_used = 0
                    for q in db_qs:
                        if len(questions) >= count:
                            break
                        qt = q.get('question_text', '').strip()
                        ans = (q.get('correct_answer') or '').strip()
                        if not qt or not ans:
                            continue
                        # Fill blank to get a complete declarative sentence
                        stmt = re.sub(r'_{5,}', ans, qt, count=1)
                        # Strip leading instruction prefix ("Complete the sentence:", etc.)
                        stmt = re.sub(
                            r'^(?:Complete\s+the\s+sentence\s*:?\s*|'
                            r'Fill\s+in\s+the\s+blank\s*:?\s*)',
                            '', stmt, flags=re.IGNORECASE
                        ).strip()
                        # Repair OCR spaced-char artifacts stored in module_questions
                        stmt = ExamGenerator._fix_spaced_characters(stmt)
                        stmt = ExamGenerator._desquish_long_tokens(stmt)
                        if len(stmt.split()) < 3:
                            continue
                        # Reject if still contains concatenated artifact (wordninja failed)
                        if any(len(w) > 20 and w.isalpha() for w in stmt.split()):
                            continue
                        if not stmt or len(stmt.split()) < 5:
                            continue
                        # True version
                        if true_used < true_budget:
                            q_true = {
                                'question_text': stmt,
                                'question_type': 'true_false',
                                'difficulty_level': difficulty,
                                'correct_answer': 'True',
                                'points': points,
                                'bloom_level': bloom_level,
                                '_module_question_id': q.get('_module_question_id'),
                                '_image_id': q.get('_image_id'),
                            }
                            if self._add_question_if_valid(q_true):
                                questions.append(q_true)
                                true_used += 1
                        # False version (negate)
                        if false_used < false_budget and len(questions) < count:
                            modified = self._create_false_statement(stmt)
                            if modified:
                                q_false = {
                                    'question_text': modified,
                                    'question_type': 'true_false',
                                    'difficulty_level': difficulty,
                                    'correct_answer': 'False',
                                    'points': points,
                                    'bloom_level': bloom_level,
                                }
                                if self._add_question_if_valid(q_false):
                                    questions.append(q_false)
                                    false_used += 1
                return questions

            random.shuffle(sentences)

            # Enforce balanced True/False mix — at most ceil(count/2) of each type
            true_budget  = (count + 1) // 2
            false_budget = count // 2
            true_used    = 0
            false_used   = 0

            # Prefer clue-based statements so the output is anchored in the module
            # without copying full source sentences verbatim.
            self.tfidf_engine.add_document(clean_text)
            tfidf_keywords = self.tfidf_engine.extract_keywords(clean_text, top_n=max(count * 6, 12))
            clue_pairs = []
            seen_keywords = set()
            for keyword, _ in self._enhance_keyword_selection_with_nlp(clean_text, tfidf_keywords):
                kw_key = keyword.lower().strip()
                if not kw_key or kw_key in seen_keywords:
                    continue
                if self._is_low_quality_objective_answer(keyword, question_type='true_false'):
                    continue
                clue = self._extract_question_clue(clean_text, keyword)
                if not clue:
                    continue
                clue_pairs.append((keyword, clue))
                seen_keywords.add(kw_key)
                if len(clue_pairs) >= count * 4:
                    break

            random.shuffle(clue_pairs)
            for keyword, clue in clue_pairs:
                if len(questions) >= count:
                    break

                if true_used < true_budget:
                    statement = self._build_true_false_statement_from_clue(keyword, clue)
                    if statement:
                        q_true = {
                            'question_text': statement,
                            'question_type': 'true_false',
                            'difficulty_level': difficulty,
                            'correct_answer': 'True',
                            'points': points,
                            'bloom_level': bloom_level
                        }
                        if self._add_question_if_valid(q_true):
                            questions.append(q_true)
                            true_used += 1

                if false_used < false_budget and len(questions) < count:
                    other_pairs = [
                        pair for pair in clue_pairs
                        if pair[0].lower() != keyword.lower()
                    ]
                    if other_pairs:
                        wrong_keyword, _ = random.choice(other_pairs)
                        statement = self._build_true_false_statement_from_clue(wrong_keyword, clue)
                        if statement:
                            q_false = {
                                'question_text': statement,
                                'question_type': 'true_false',
                                'difficulty_level': difficulty,
                                'correct_answer': 'False',
                                'points': points,
                                'bloom_level': bloom_level
                            }
                            if self._add_question_if_valid(q_false):
                                questions.append(q_false)
                                false_used += 1

            _tf_prefixes = [
                "", "", "", "",  # 4x no prefix (most T/F are plain statements)
                "State whether the statement is correct: ",
                "Determine whether the statement is accurate: ",
                "Evaluate the accuracy of this statement: ",
                "Judge the accuracy of this statement: ",
            ]

            # Try BOTH a True and a False question from every sentence so a small
            # sentence pool (N sentences) can still produce 2N candidate questions.
            for sentence in sentences:
                if len(questions) >= count:
                    break

                # --- True version (respect budget) ---
                if true_used < true_budget:
                    _tf_stmt = ExamGenerator._desquish_long_tokens(sentence)
                    _tf_prefix = random.choice(_tf_prefixes)
                    q_true = {
                        'question_text': f"{_tf_prefix}{_tf_stmt}" if _tf_prefix else _tf_stmt,
                        'question_type': 'true_false',
                        'difficulty_level': difficulty,
                        'correct_answer': 'True',
                        'points': points,
                        'bloom_level': bloom_level
                    }
                    if self._add_question_if_valid(q_true):
                        questions.append(q_true)
                        true_used += 1

                if len(questions) >= count:
                    break

                # --- False version (negate the same sentence, respect budget) ---
                if false_used < false_budget:
                    modified = self._create_false_statement(sentence)
                    if modified:
                        _tf_stmt_f = ExamGenerator._desquish_long_tokens(modified)
                        _tf_prefix_f = random.choice(_tf_prefixes)
                        q_false = {
                            'question_text': f"{_tf_prefix_f}{_tf_stmt_f}" if _tf_prefix_f else _tf_stmt_f,
                            'question_type': 'true_false',
                            'difficulty_level': difficulty,
                            'correct_answer': 'False',
                            'points': points,
                            'bloom_level': bloom_level
                        }
                        if self._add_question_if_valid(q_false):
                            questions.append(q_false)
                            false_used += 1

            # ── Keyword-definition fallback ───────────────────────────────────
            # When the sentence pool is exhausted but we're still short of the
            # target, extract definition sentences for each TF-IDF keyword and
            # use those as additional True/False statements.
            if len(questions) < count:
                logger.info(f"        ℹ️  Sentence pool exhausted — trying keyword-definition fallback")
                self.tfidf_engine.add_document(clean_text)
                kw_fallback = self.tfidf_engine.extract_keywords(clean_text, top_n=count * 3)
                seen_def_sents: set = set()

                for kw, _ in kw_fallback:
                    if len(questions) >= count:
                        break
                    def_sent = self._extract_definition_sentence(clean_text, kw)
                    if not def_sent or def_sent in seen_def_sents:
                        continue
                    if self._is_low_quality_objective_answer(kw, question_type='true_false'):
                        continue
                    seen_def_sents.add(def_sent)
                    clue = self._extract_question_clue(clean_text, kw)
                    def_clean = self._build_true_false_statement_from_clue(kw, clue)
                    if not ExamGenerator._is_valid_question_sentence(def_sent.rstrip('.')):
                        continue
                    if not def_clean:
                        continue

                    if true_used < true_budget:
                        q_t = {
                            'question_text': def_clean,
                            'question_type': 'true_false',
                            'difficulty_level': difficulty,
                            'correct_answer': 'True',
                            'points': points,
                            'bloom_level': bloom_level
                        }
                        if self._add_question_if_valid(q_t):
                            questions.append(q_t)
                            true_used += 1

                    if len(questions) < count and false_used < false_budget:
                        modified = self._create_false_statement(def_clean)
                        if modified:
                            q_f = {
                                'question_text': modified,
                                'question_type': 'true_false',
                                'difficulty_level': difficulty,
                                'correct_answer': 'False',
                                'points': points,
                                'bloom_level': bloom_level
                            }
                            if self._add_question_if_valid(q_f):
                                questions.append(q_f)
                                false_used += 1

            # ── FIX: Keyword-swap fallback for remaining False budget ─────────
            # When _create_false_statement() returns None for all sentences
            # (e.g. text has no copula verbs), the false_budget stays unfilled.
            # This fallback swaps a TF-IDF keyword with a different keyword so
            # the statement becomes factually incorrect.
            if false_used < false_budget and len(questions) < count:
                logger.info(
                    f"        ℹ️  Negation fallback exhausted — "
                    f"using keyword-swap for {false_budget - false_used} remaining False questions"
                )
                self.tfidf_engine.add_document(clean_text)
                kw_list = self.tfidf_engine.extract_keywords(clean_text, top_n=60)
                kw_words = [k for k, _ in kw_list]

                for sentence in sentences:
                    if false_used >= false_budget or len(questions) >= count:
                        break
                    swapped = False
                    for kw in kw_words:
                        if swapped:
                            break
                        other_kws = [k for k in kw_words if k.lower() != kw.lower()]
                        if not other_kws:
                            continue
                        if re.search(r'\b' + re.escape(kw) + r'\b', sentence, re.IGNORECASE):
                            swap_word = random.choice(other_kws)
                            modified = re.sub(
                                r'\b' + re.escape(kw) + r'\b',
                                swap_word, sentence, count=1, flags=re.IGNORECASE
                            )
                            if modified == sentence:
                                continue
                            q_false = {
                                'question_text': modified,
                                'question_type': 'true_false',
                                'difficulty_level': difficulty,
                                'correct_answer': 'False',
                                'points': points,
                                'bloom_level': bloom_level
                            }
                            if self._add_question_if_valid(q_false):
                                questions.append(q_false)
                                false_used += 1
                                swapped = True
                                logger.info(
                                    f"        🔄 Keyword-swap False: "
                                    f"'{kw}' → '{swap_word}'"
                                )

            true_count = sum(1 for q in questions if q['correct_answer'] == 'True')
            false_count = len(questions) - true_count
            logger.info(f"        ℹ️  Mix: {true_count} True, {false_count} False")
            # Shuffle final set so True/False aren't clustered in UI
            random.shuffle(questions)
            logger.info(f"        ✅ Generated {len(questions)}/{count}")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error: {str(e)}")
            return []

    def _create_false_statement(self, sentence):
        """
        Create a false version of a sentence by intelligent negation.

        Tries progressively:
          1. spaCy dependency-aware negation (ROOT verb + auxiliary detection)
          2. Hardcoded copula / auxiliary negation patterns
          3. 3rd-person singular verb negation
          4. FIX: Passive voice patterns (are used, is called, etc.)
          5. FIX: Quantity / degree substitution (less than → more than, average → maximum)
        Returns None if no negation rule applies.
        """
        try:
            s = sentence
            has_not = ' not ' in s or " n't" in s

            # ── spaCy dependency-aware negation (primary, when NLP is loaded) ─
            if not has_not:
                try:
                    nlp = self._get_spacy_nlp()
                    if nlp:
                        doc = nlp(s)
                        for token in doc:
                            if token.dep_ == 'ROOT' and token.pos_ == 'VERB':
                                # Prefer inserting after the first auxiliary child
                                aux_tokens = [t for t in token.children if t.dep_ in ('aux', 'auxpass')]
                                if aux_tokens:
                                    aux = aux_tokens[0]
                                    return s.replace(aux.text, aux.text + ' not', 1)
                                # Otherwise negate the ROOT verb directly using its lemma
                                return s.replace(token.text, 'does not ' + token.lemma_, 1)
                except Exception:
                    pass  # fall through to hardcoded rules

            # ── Remove existing negation (already-negative sentences → make positive) ─
            if ' is not ' in s:
                return s.replace(' is not ', ' is ', 1)
            if ' are not ' in s:
                return s.replace(' are not ', ' are ', 1)
            if ' was not ' in s:
                return s.replace(' was not ', ' was ', 1)
            if ' were not ' in s:
                return s.replace(' were not ', ' were ', 1)
            if ' cannot ' in s:
                return s.replace(' cannot ', ' can ', 1)
            if ' does not ' in s:
                return s.replace(' does not ', ' does ', 1)
            if ' do not ' in s:
                return s.replace(' do not ', ' do ', 1)
            if ' did not ' in s:
                return s.replace(' did not ', ' did ', 1)
            if ' should not ' in s:
                return s.replace(' should not ', ' should ', 1)
            if ' will not ' in s:
                return s.replace(' will not ', ' will ', 1)
            if ' has not ' in s:
                return s.replace(' has not ', ' has ', 1)
            if ' have not ' in s:
                return s.replace(' have not ', ' have ', 1)

            if not has_not:
                # ── Copula / auxiliary verbs ──────────────────────────────────
                if ' is ' in s:
                    return s.replace(' is ', ' is not ', 1)
                if ' are ' in s:
                    return s.replace(' are ', ' are not ', 1)
                if ' was ' in s:
                    return s.replace(' was ', ' was not ', 1)
                if ' were ' in s:
                    return s.replace(' were ', ' were not ', 1)
                if ' can ' in s:
                    return s.replace(' can ', ' cannot ', 1)
                if ' will ' in s:
                    return s.replace(' will ', ' will not ', 1)
                if ' has ' in s:
                    return s.replace(' has ', ' has not ', 1)
                if ' have ' in s:
                    return s.replace(' have ', ' have not ', 1)

                # ── 3rd-person singular verbs (educational content) ───────────
                for v in ['shows', 'indicates', 'represents', 'provides',
                          'includes', 'contains', 'requires', 'uses', 'means',
                          'refers', 'allows', 'helps', 'causes', 'makes',
                          'defines', 'describes', 'determines', 'measures',
                          'follows', 'depends', 'applies', 'results']:
                    if f' {v} ' in s:
                        return s.replace(f' {v} ', f' does not {v} ', 1)

                # ── FIX: Passive voice patterns ───────────────────────────────
                if ' are used ' in s:
                    return s.replace(' are used ', ' are not used ', 1)
                if ' is used ' in s:
                    return s.replace(' is used ', ' is not used ', 1)
                if ' are called ' in s:
                    return s.replace(' are called ', ' are not called ', 1)
                if ' is called ' in s:
                    return s.replace(' is called ', ' is not called ', 1)
                if ' are known ' in s:
                    return s.replace(' are known ', ' are not known ', 1)
                if ' is known ' in s:
                    return s.replace(' is known ', ' is not known ', 1)
                if ' are considered ' in s:
                    return s.replace(' are considered ', ' are not considered ', 1)
                if ' is considered ' in s:
                    return s.replace(' is considered ', ' is not considered ', 1)
                if ' are defined ' in s:
                    return s.replace(' are defined ', ' are not defined ', 1)
                if ' is defined ' in s:
                    return s.replace(' is defined ', ' is not defined ', 1)
                if ' became ' in s:
                    return s.replace(' became ', ' did not become ', 1)
                if ' become ' in s:
                    return s.replace(' become ', ' does not become ', 1)

                # ── FIX: Quantity / degree substitution ───────────────────────
                if 'less than' in s:
                    return s.replace('less than', 'more than', 1)
                if 'more than' in s:
                    return s.replace('more than', 'less than', 1)
                if 'at least' in s:
                    return s.replace('at least', 'at most', 1)
                if 'at most' in s:
                    return s.replace('at most', 'at least', 1)
                if ' average ' in s:
                    return s.replace(' average ', ' maximum ', 1)
                if ' minimum ' in s:
                    return s.replace(' minimum ', ' maximum ', 1)
                if ' maximum ' in s:
                    return s.replace(' maximum ', ' minimum ', 1)
                if ' always ' in s:
                    return s.replace(' always ', ' never ', 1)
                if ' never ' in s:
                    return s.replace(' never ', ' always ', 1)
                if ' all ' in s:
                    return s.replace(' all ', ' no ', 1)
                if ' every ' in s:
                    return s.replace(' every ', ' no ', 1)

            # ── Symbolic relations (formula/query notation) ──────────────────
            # Handles cases like:
            #   "?- f(X) = f(a), X = b." -> "?- f(X) != f(a), X = b."
            if '!=' in s:
                return s.replace('!=', '=', 1)
            if ' ≠ ' in s:
                return s.replace(' ≠ ', ' = ', 1)
            eq_match = re.search(r'(?<![<>=!])=(?!=)', s)
            if eq_match:
                return s[:eq_match.start()] + '!=' + s[eq_match.end():]

            # ── WordNet antonym substitution (last resort before giving up) ──
            # POS-tag the sentence and attempt to swap a key adjective, verb,
            # or adverb with its WordNet antonym for a semantically valid
            # false statement (e.g. "efficient" → "inefficient").
            try:
                tagged = pos_tag(word_tokenize(s))
                for word, tag in tagged:
                    if len(word) < 3:
                        continue
                    # Only adjectives (JJ*), verbs (VB*), adverbs (RB*)
                    if tag.startswith(('JJ', 'VB', 'RB')):
                        antonyms = self._get_wordnet_antonyms(word)
                        if antonyms:
                            antonym = antonyms[0]
                            result = s.replace(word, antonym, 1)
                            if result != s:
                                logger.info(f"        ✅ WordNet antonym: '{word}' → '{antonym}'")
                                return result
            except Exception:
                pass

            # Final fallback: force a false statement instead of skipping.
            normalized = (s or '').strip()
            if normalized:
                if normalized[-1] in '.!?':
                    normalized = normalized[:-1].rstrip()
                fallback = f"It is false that {normalized}."
                logger.info("        ℹ️  Fallback negation used")
                return fallback

            logger.warning(f"        ⚠️  Could not negate sentence: '{s[:80]}'")
            return None
        except Exception as e:
            logger.warning(f"        ⚠️  Exception in _create_false_statement: {e}")
            return None
    
    def _generate_fill_in_blank(self, text_content, difficulty, count, points,
                               bloom_level='remembering', module_ids=None):
        """
        IMPROVED: Target important keywords, not grammar words
        AI ENHANCEMENT: Uses spaCy POS tagging for intelligent blank selection
        DB-FIRST: Pulls pre-processed factual questions from module_questions table.
        """
        logger.info(f"        📝 Generating {count} Fill-in-Blank ({difficulty})...")
        questions = []

        try:
            # DB-first: pull stored questions (all types) and convert to fill-in-blank.
            # Only keep questions with short answers (≤5 words) — this rejects
            # conceptual/analysis questions with paragraph answers that produce bad FIBs.
            _FIB_DB_SKIP = frozenset({
                'exam', 'data', 'bits', 'field', 'host', 'hosts', 'count', 'route',
                'type', 'mode', 'node', 'link', 'unit', 'form', 'term', 'code', 'role',
                'rate', 'base', 'case', 'item', 'list', 'name', 'part', 'step', 'time',
                'area', 'cost', 'side', 'note', 'line', 'text', 'word', 'file', 'page',
                'user', 'need', 'class', 'level', 'point', 'group', 'order', 'layer',
                'hops', 'nic', 'mac', 'rip', 'tcp', 'udp', 'bit', 'net', 'lan', 'wan',
                'ip', 'arp', 'size', 'port', 'flag', 'byte', 'used', 'best', 'does',
                'ccna', 'ccnp', 'ccie', 'number', 'cable', 'value', 'means',
                'rejected', 'screen', 'metro', 'summation', 'positive', 'negative',
            })

            def _fib_from_db(pool):
                for q in pool:
                    if len(questions) >= count:
                        break
                    ans = (q.get('correct_answer') or '').strip()
                    if not ans or len(ans.split()) > 6:
                        continue  # skip long / missing answers
                    # Skip single-word generic answers
                    if len(ans.split()) == 1 and ans.lower() in _FIB_DB_SKIP:
                        continue
                    # Single-word answers must be at least 3 chars
                    if len(ans.split()) == 1 and len(ans) < 3:
                        continue
                    qt = (q.get('question_text') or '').strip()
                    if not qt:
                        continue
                    if re.search(r'_{5,}', qt):
                        fib_text = qt
                    else:
                        try:
                            blanked = re.sub(re.escape(ans), '_______', qt, count=1, flags=re.IGNORECASE)
                        except re.error:
                            blanked = qt
                        if '_______' in blanked and blanked != qt:
                            fib_text = blanked
                        elif len(qt.split()) >= 3:
                            stem = re.sub(r'\?\s*$', '', qt).strip()
                            fib_text = f"{stem}: _______"
                        else:
                            continue
                    fib_q = {**q, 'question_text': fib_text, 'question_type': 'fill_in_blank'}
                    if self._add_question_if_valid(fib_q):
                        questions.append(fib_q)

            if module_ids:
                db_qs = self._query_module_questions(module_ids, None, difficulty, count * 4, points=points)
                _fib_from_db(db_qs)
                # If the exact-difficulty pool was insufficient, supplement with any difficulty
                if len(questions) < count:
                    db_qs2 = self._query_module_questions(module_ids, None, None, (count - len(questions)) * 4, points=points)
                    _fib_from_db(db_qs2)
                if len(questions) >= count:
                    logger.info(f"        ✅ DB-first satisfied all {count} fill_in_blank questions")
                    return questions[:count]
                count -= len(questions)

            # Clean text first
            clean_text = self._clean_text_for_questions(text_content)

            sentences = [
                s for s in self._sent_tokenize(clean_text)
                if 20 < len(s) < 350
                and ExamGenerator._is_valid_question_sentence(s)
            ]

            if not sentences:
                logger.info("        ℹ️  No valid sentences for FIB text gen; trying clue-based generation only")

            # Get important keywords
            self.tfidf_engine.add_document(clean_text)
            tfidf_keywords = self.tfidf_engine.extract_keywords(clean_text, top_n=count * 5)

            # AI ENHANCEMENT: Enhance with linguistic features
            keywords = self._enhance_keyword_selection_with_nlp(clean_text, tfidf_keywords)
            keyword_list = [k.lower() for k, _ in keywords]

            logger.info(f"        ℹ️  Identified {len(keyword_list)} important keywords (AI-enhanced)")

            # AI ENHANCEMENT: Use spaCy for smarter blank selection
            nlp = self._get_spacy_nlp()

            # Words that produce poor FIB answers — generic verbs, adjectives,
            # logical primitives, and common function-word fragments
            _FIB_SKIP_WORDS = {
                # generic gerunds / participles
                'using', 'testing', 'making', 'finding', 'taking', 'getting',
                'giving', 'showing', 'having', 'being', 'doing', 'following',
                'conducting', 'including', 'providing', 'indicating',
                # generic adjectives / determiners
                'possible', 'correct', 'available', 'different', 'certain',
                'specific', 'various', 'important', 'necessary', 'general',
                'absolute', 'entire', 'thorough', 'indicated',
                # logical/boolean primitives
                'null', 'true', 'false', 'none', 'both', 'each', 'other',
                'same', 'such', 'also', 'given', 'known', 'based', 'used',
                # instruction verbs
                'reject', 'accept', 'write', 'solve', 'compute', 'determine',
                'consider', 'identify', 'note', 'check', 'compare', 'state',
            }

            # Prefer clue-based blanks first so the prompt tests understanding
            # instead of reproducing a module sentence almost verbatim.
            used_answers = {q.get('correct_answer', '').lower() for q in questions}
            for keyword, _ in keywords:
                if len(questions) >= count:
                    break

                kw_key = keyword.lower().strip()
                if not kw_key or kw_key in used_answers:
                    continue
                if kw_key in _FIB_SKIP_WORDS:
                    continue
                if self._is_low_quality_objective_answer(keyword, question_type='fill_in_blank'):
                    continue
                if len(kw_key.replace(' ', '')) < 4:
                    continue

                clue = self._extract_question_clue(clean_text, keyword)
                stem = self._build_fill_in_blank_stem_from_clue(clue, bloom_level)
                if not stem:
                    continue

                question = {
                    'question_text': stem,
                    'question_type': 'fill_in_blank',
                    'difficulty_level': difficulty,
                    'correct_answer': keyword,
                    'points': points,
                    'bloom_level': bloom_level
                }

                if self._add_question_if_valid(question):
                    questions.append(question)
                    used_answers.add(kw_key)

            for sentence in sentences:
                if len(questions) >= count:
                    break

                # AI ENHANCEMENT: Analyze sentence with spaCy
                if nlp:
                    try:
                        doc = nlp(sentence)
                        blank_candidates = []

                        for i, token in enumerate(doc):
                            word_clean = token.text.lower()

                            # Only blank NOUN/PROPN by default.
                            # VERB and ADJ are only eligible when they are an
                            # explicitly recognised keyword (domain-specific term).
                            is_keyword = word_clean in keyword_list
                            is_noun = token.pos_ in ['NOUN', 'PROPN']
                            is_content_verb_adj = token.pos_ in ['VERB', 'ADJ'] and is_keyword
                            is_important_pos = is_noun or is_content_verb_adj
                            is_important_dep = token.dep_ in ['nsubj', 'dobj', 'pobj', 'ROOT']

                            if (is_important_pos and len(word_clean) > 3 and
                                word_clean not in _FIB_SKIP_WORDS and
                                word_clean not in ['which', 'where', 'there', 'these', 'those', 'their', 'would', 'could', 'should',
                                                   'that', 'this', 'with', 'from', 'have', 'been', 'were', 'will', 'than'] and
                                i not in [0, len(doc)-1]):

                                # Calculate priority score
                                priority = 0
                                if is_keyword:
                                    priority += 3
                                if is_important_dep:
                                    priority += 2
                                if token.pos_ in ['NOUN', 'PROPN']:
                                    priority += 2
                                elif token.pos_ == 'VERB':
                                    priority += 1

                                blank_candidates.append((i, token.text, priority))

                        if blank_candidates:
                            # Sort by priority and try MULTIPLE blanks from the same
                            # sentence so a small sentence pool still hits the target count
                            blank_candidates.sort(key=lambda x: x[2], reverse=True)
                            for blank_index, blank_word, priority in blank_candidates:
                                if len(questions) >= count:
                                    break
                                blank_word_clean = re.sub(r'[^\w]', '', blank_word)
                                if not blank_word_clean:
                                    continue
                                if self._is_low_quality_objective_answer(blank_word_clean, question_type='fill_in_blank'):
                                    continue

                                blanked_sentence = ' '.join(
                                    '______' if j == blank_index else token.text
                                    for j, token in enumerate(doc)
                                )

                                _fib_prefixes = [
                                    "", "", "",  # 3x no prefix for variety
                                    "Complete the statement: ",
                                    "Fill in the blank: ",
                                    "Supply the missing word: ",
                                    "Provide the correct term: ",
                                    "Write the missing word: ",
                                    "What word completes the sentence? ",
                                    "Give the missing term: ",
                                ]
                                _prefix = random.choice(_fib_prefixes)
                                question = {
                                    'question_text': f"{_prefix}{blanked_sentence}" if _prefix else blanked_sentence,
                                    'question_type': 'fill_in_blank',
                                    'difficulty_level': difficulty,
                                    'correct_answer': blank_word_clean,
                                    'points': points,
                                    'bloom_level': bloom_level
                                }

                                if self._add_question_if_valid(question):
                                    questions.append(question)
                                    logger.info(f"        🎯 AI-selected blank: {blank_word} (priority: {priority})")
                            continue

                    except Exception as nlp_error:
                        logger.warning(f"        ⚠️ spaCy processing failed, using fallback: {nlp_error}")

            # FALLBACK: Original method if spaCy fails
            words = sentence.split()
            blank_candidates = []
            for i, word in enumerate(words):
                word_clean = re.sub(r'[^\w]', '', word).lower()

                if (len(word_clean) > 4 and
                        word_clean not in _FIB_SKIP_WORDS and
                        word_clean not in ['which', 'where', 'there', 'these', 'those', 'their', 'would', 'could', 'should'] and
                        i not in [0, len(words)-1]):

                        priority = 2 if word_clean in keyword_list else 1
                        blank_candidates.append((i, word, priority))

                if not blank_candidates:
                    continue

                # Try multiple blanks per sentence (same idea as spaCy path)
                blank_candidates.sort(key=lambda x: x[2], reverse=True)
                for blank_index, blank_word, _ in blank_candidates:
                    if len(questions) >= count:
                        break
                    blank_word_clean = re.sub(r'[^\w]', '', blank_word)
                    if not blank_word_clean:
                        continue
                    if self._is_low_quality_objective_answer(blank_word_clean, question_type='fill_in_blank'):
                        continue

                    blanked_sentence = ' '.join(
                        '______' if j == blank_index else w
                        for j, w in enumerate(words)
                    )

                    question = {
                        'question_text': blanked_sentence,
                        'question_type': 'fill_in_blank',
                        'difficulty_level': difficulty,
                        'correct_answer': blank_word_clean,
                        'points': points,
                        'bloom_level': bloom_level
                    }

                    if self._add_question_if_valid(question):
                        questions.append(question)

            # Starter-based top-up if still short
            remaining = count - len(questions)
            if remaining > 0 and keyword_list:
                used_answers = set(q.get('correct_answer', '').lower() for q in questions)
                starters = list(self.FILL_BLANK_STARTERS)
                random.shuffle(starters)
                kw_iter = iter(keyword_list)
                while remaining > 0:
                    try:
                        kw = next(kw_iter)
                    except StopIteration:
                        break
                    if kw in used_answers:
                        continue
                    stem = random.choice(starters) if starters else "The _______ is"
                    if '_______' not in stem:
                        stem = stem + " _______"
                    question = {
                        'question_text': stem,
                        'question_type': 'fill_in_blank',
                        'difficulty_level': difficulty,
                        'correct_answer': kw,
                        'points': points,
                        'bloom_level': bloom_level
                    }
                    if self._add_question_if_valid(question):
                        questions.append(question)
                        used_answers.add(kw)
                        remaining -= 1
                if remaining > 0:
                    logger.warning(f"        ⚠️  FIB starter top-up still short by {remaining}")

            logger.info(f"        ✅ Generated {len(questions)}/{count}")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error: {str(e)}")
            return []
    
    def _generate_identification(self, text_content, difficulty, count, points,
                                bloom_level='remembering', module_ids=None):
        """
        CRITICAL FIX: Clean identification questions
        AI ENHANCEMENT: Uses spaCy and transformers for better keyword extraction
        DB-FIRST: Pulls pre-processed factual questions from module_questions table.

        OLD PROBLEM:
        - "Based on 'PRELIMINARY ACTIVITIES IV. MAC address is...' - Identify the term"

        NEW SOLUTION:
        - "A physical address that uniquely identifies each device on a network. What is this?"
        """
        logger.info(f"        📝 Generating {count} Identification ({difficulty})...")
        questions = []

        try:
            # DB-first: pull stored identification-style questions (all types).
            # Supplement with any difficulty when the exact-difficulty pool is small.
            # Filter out questions whose correct_answer is a generic/short word
            # that would produce meaningless stems like "Define exam" or "What is bits?"
            _DB_ID_SKIP = frozenset({
                'exam', 'data', 'bits', 'field', 'host', 'hosts', 'count', 'route',
                'type', 'mode', 'node', 'link', 'unit', 'form', 'term', 'code', 'role',
                'rate', 'base', 'case', 'item', 'list', 'name', 'part', 'step', 'time',
                'area', 'cost', 'side', 'note', 'line', 'text', 'word', 'file', 'page',
                'user', 'need', 'class', 'level', 'point', 'group', 'order', 'layer',
                'hops', 'nic', 'mac', 'rip', 'tcp', 'udp', 'bit', 'net', 'lan', 'wan',
                'ip', 'arp', 'size', 'port', 'flag', 'byte', 'used',
                'ccna', 'ccnp', 'ccie', 'number', 'cable', 'value',
                'network', 'networks', 'address', 'borrowing',
            })

            def _id_from_db(pool):
                for q in pool:
                    if len(questions) >= count:
                        break
                    # Skip questions with generic/short correct_answer
                    ans_raw = (q.get('correct_answer') or '').strip()
                    ans = ans_raw.lower()
                    if ans in _DB_ID_SKIP:
                        continue
                    # Single-word answers must be at least 4 chars
                    if ' ' not in ans and len(ans) < 4:
                        continue
                    # Identification answers must be SHORT (≤ 18 words).
                    # Essay/paragraph answers are not identification-style.
                    ans_word_count = len(ans_raw.split())
                    if ans_word_count > 18:
                        continue
                    # Skip questions with squished-text artifacts in question_text
                    qt = (q.get('question_text') or '')
                    qt_lower = qt.lower()
                    # Skip low-quality stems we know we later reject
                    # if "complete the sentence" in qt_lower or "what term completes" in qt_lower:
                    #     continue
                    # Skip if the answer leaks into the stem
                    if ans and len(ans) >= 4 and ans in qt_lower:
                        continue
                    if any(len(w.rstrip(".,;:!?'\"")) > 25 and w.rstrip(".,;:!?'\"").isalpha() for w in qt.split()):
                        continue
                    if self._add_question_if_valid(q):
                        questions.append(q)

            if module_ids:
                db_qs = self._query_module_questions(module_ids, None, difficulty, count * 4, target_type='identification', points=points)
                _id_from_db(db_qs)
                # Supplement with questions from other difficulty levels when short
                if len(questions) < count:
                    db_qs2 = self._query_module_questions(module_ids, None, None, (count - len(questions)) * 4, target_type='identification', points=points)
                    _id_from_db(db_qs2)
                if len(questions) >= count:
                    logger.info(f"        ✅ DB-first satisfied all {count} identification questions")
                    return questions[:count]
                count -= len(questions)

            # Extract important keywords
            top_n = count * 5
            clean_text = self._clean_text_for_questions(text_content)

            self.tfidf_engine.add_document(clean_text)
            tfidf_keywords = self.tfidf_engine.extract_keywords(clean_text, top_n=top_n)

            if not tfidf_keywords:
                logger.warning(f"        ⚠️  No keywords extracted")
                return questions  # Return whatever DB questions were collected

            # AI ENHANCEMENT: Enhance keywords with spaCy linguistic analysis
            keywords = self._enhance_keyword_selection_with_nlp(clean_text, tfidf_keywords)

            logger.info(f"        ℹ️  Identified {len(keywords)} important keywords (AI-enhanced)")

            # Prefer multi-word compound phrases over their component words.
            # If "hypothesis testing" is in the list, drop bare "hypothesis" and "testing".
            multi_word_phrases = {kw.lower() for kw, _ in keywords if ' ' in kw}
            keywords = [
                (kw, sc) for kw, sc in keywords
                if ' ' in kw  # always keep phrases
                or not any(kw.lower() in phrase for phrase in multi_word_phrases)
            ]

            # Shuffle keywords for variety
            shuffled_keywords = list(keywords)
            random.shuffle(shuffled_keywords)

            # Words that must never be an identification answer:
            # - bare gerunds / participles that are sub-components of a phrase
            # - logical/boolean primitives
            # - articles/prepositions that TF-IDF sometimes scores
            # - generic single-concept words (need, bits, number, etc.) that produce
            #   meaningless stems like "Describe the function of need"
            _IDENTIFICATION_SKIP_WORDS = {
                'using', 'testing', 'making', 'finding', 'taking', 'getting',
                'giving', 'showing', 'having', 'being', 'doing', 'based',
                'given', 'known', 'used', 'made', 'done', 'called', 'named',
                'null', 'true', 'false', 'none', 'both', 'each', 'other',
                'such', 'same', 'different', 'following', 'above', 'below',
                'first', 'second', 'third', 'last', 'next', 'also',
                'however', 'therefore', 'thus', 'hence', 'whereas',
                'example', 'note', 'figure', 'table', 'section',
                # Generic structural / measurement words that make bad ID stems
                'need', 'bits', 'number', 'class', 'field', 'value', 'level',
                'point', 'order', 'layer', 'group', 'route', 'count', 'cable',
                'mode', 'type', 'size', 'node', 'link', 'unit', 'form', 'term',
                'code', 'role', 'rate', 'base', 'case', 'item', 'list', 'name',
                'part', 'step', 'time', 'area', 'cost', 'side', 'line', 'text',
                'word', 'file', 'page', 'user', 'host', 'hops', 'byte', 'flag',
                'port', 'data', 'exam', 'bits', 'nic', 'mac', 'rip', 'ip',
                'lan', 'wan', 'net', 'bit', 'tcp', 'udp', 'arp',
            }

            # Track answers used within this batch to prevent duplicates
            _used_id_answers = set(q.get('correct_answer', '').lower() for q in questions)

            for keyword, score in shuffled_keywords:
                if len(questions) >= count:
                    break

                # Skip generic/ambiguous terms that make poor identification answers
                kw_lower = keyword.lower().strip()
                if kw_lower in _IDENTIFICATION_SKIP_WORDS:
                    continue
                if self._is_low_quality_objective_answer(keyword, question_type='identification'):
                    continue
                # Skip single-word answers that are just verb gerunds (ending in -ing, < 8 chars)
                if len(kw_lower) < 8 and kw_lower.endswith('ing') and ' ' not in kw_lower:
                    continue
                # Skip very short tokens (less than 5 meaningful characters for single words,
                # 4 for multi-word phrases where each component is meaningful)
                stripped_len = len(kw_lower.replace(' ', ''))
                if stripped_len < 5 and ' ' not in kw_lower:
                    continue
                if stripped_len < 4:
                    continue
                # Skip generic article+noun phrases that are ≤ 2 words and start with a/an/the
                # e.g. "a method", "the sample", "a population", "a conjecture"
                kw_words = kw_lower.split()
                if len(kw_words) <= 2 and kw_words[0] in ('a', 'an', 'the'):
                    continue

                # Reset per-iteration context so QA never uses a stale value from a previous loop
                best_context = None

                # Try to find a definition sentence first
                definition_sentence = self._extract_definition_sentence(clean_text, keyword)
                clean_description = None

                if definition_sentence:
                    clean_description = self._create_clean_description(definition_sentence, keyword)
                    # Use definition sentence as QA context when definition path is taken
                    best_context = definition_sentence

                if clean_description and len(clean_description) >= 15:
                    # High-quality: definition-based question
                    question_templates = [
                        f"{clean_description}. What is this called?",
                        f"Identify the term: {clean_description}",
                        f"{clean_description}. Identify the term being described.",
                        f"What term refers to: {clean_description}?",
                        f"What concept is described here? {clean_description}",
                        f"Give the term for the following: {clean_description}.",
                        f"Name the term: {clean_description}.",
                        f"{clean_description}. What is the correct term for this?",
                        f"What is the term used for: {clean_description}?",
                        f"Based on the description, identify the term: {clean_description}.",
                        f"{clean_description}. Name this concept.",
                        f"What do we call the following? {clean_description}",
                        f"Provide the term for: {clean_description}.",
                        f"{clean_description}. What is this known as?",
                        f"Which term matches this description? {clean_description}",
                        f"State the term described: {clean_description}.",
                        f"{clean_description}. Give the correct term.",
                        f"What is the name for: {clean_description}?",
                        f"Identify the concept: {clean_description}.",
                        f"{clean_description}. What term applies here?",
                        f"What term describes this? {clean_description}",
                        f"Define the term: {clean_description}.",
                        f"{clean_description}. Identify this term.",
                        f"Provide the correct term: {clean_description}.",
                        f"What is being described? {clean_description}",
                        f"{clean_description}. What concept does this refer to?",
                        f"Name the concept being described: {clean_description}.",
                        f"What term best fits this definition? {clean_description}",
                        f"{clean_description}. State the correct term.",
                        f"Give the name of the term described: {clean_description}.",
                        f"What is the proper term for: {clean_description}?",
                        f"{clean_description}. What is this referred to as?",
                        f"Identify the following: {clean_description}.",
                        f"What does this describe? {clean_description}",
                        f"{clean_description}. Supply the correct term.",
                        f"Determine the term: {clean_description}.",
                        f"What is the appropriate term for: {clean_description}?",
                        f"{clean_description}. What is the corresponding term?",
                        f"Recognize the term described: {clean_description}.",
                        f"What specific term refers to: {clean_description}?",
                        f"{clean_description}. Identify what this is called.",
                        f"State what term is being described: {clean_description}.",
                        f"What is the exact term for: {clean_description}?",
                        f"{clean_description}. What term is this?",
                        f"Recall the term for: {clean_description}.",
                        f"What key term is described here? {clean_description}",
                        f"{clean_description}. Provide the name of this term.",
                        f"Which specific term matches: {clean_description}?",
                        f"{clean_description}. What is the technical term?",
                        f"Write the term that fits: {clean_description}.",
                    ]
                    question_text = random.choice(question_templates)
                else:
                    # Fallback: use the best context sentence around the keyword
                    context_sentences = [
                        s for s in self._sent_tokenize(clean_text)
                        if re.search(r'\b' + re.escape(keyword) + r'\b', s, re.IGNORECASE)
                        and 20 < len(s) < 250
                        and s and s[0].isupper()  # reject mid-sentence fragments
                        and ExamGenerator._is_valid_question_sentence(s)
                    ]
                    if not context_sentences:
                        continue
                    best_context = max(context_sentences, key=len)
                    # Blank keyword in context as the clue
                    clue = re.sub(
                        r'\b' + re.escape(keyword) + r'\b', '_______',
                        best_context, count=1, flags=re.IGNORECASE
                    ).strip()
                    if '_______' not in clue:
                        continue
                    # Reject if blanking left a dangling article/preposition at the end
                    # e.g. "conducting a _______" → after blanking: "conducting a" trailing
                    if re.search(r'\b(?:a|an|the|in|of|by|to|for|on|at)\s+_______\s*$', clue, re.IGNORECASE):
                        continue
                    fallback_templates = [
                        f"What term completes this statement? \"{clue}\"",
                        f"Identify the missing term: {clue}",
                        f"What word correctly fills the blank in: \"{clue}\"?",
                        f"Supply the missing word: {clue}",
                        f"What is the missing term? {clue}",
                        f"Name the word that completes: {clue}",
                        f"Give the correct term: {clue}",
                        f"What belongs in the blank? {clue}",
                        f"Provide the missing word: {clue}",
                        f"Determine the missing term: {clue}",
                        f"What should replace the blank? {clue}",
                        f"State the missing word: {clue}",
                        f"What term goes in the blank? {clue}",
                        f"Fill in the missing term: {clue}",
                        f"Write the correct word: {clue}",
                        f"Identify what is missing: {clue}",
                        f"What word is needed here? {clue}",
                        f"Complete the statement: {clue}",
                        f"Supply the correct term: {clue}",
                        f"What fits the blank? {clue}",
                    ]
                    question_text = random.choice(fallback_templates)

                # DistilBERT QA: try to extract a more precise answer from context
                precise_answer = keyword
                try:
                    qa_answer = self._extract_answer_from_context(
                        context=best_context if best_context is not None else keyword,
                        question=question_text
                    )
                    if qa_answer and 1 < len(qa_answer) <= 80:
                        precise_answer = qa_answer
                except Exception:
                    pass

                precise_answer = self._sanitize_generated_text(precise_answer)
                if self._is_low_quality_objective_answer(precise_answer, question_type='identification'):
                    precise_answer = self._sanitize_generated_text(keyword)
                if self._is_low_quality_objective_answer(precise_answer, question_type='identification'):
                    continue

                # Skip if this answer was already used in another ID question (prevents duplicates)
                if precise_answer.lower() in _used_id_answers:
                    precise_answer = keyword  # fall back to raw keyword
                if precise_answer.lower() in _used_id_answers:
                    continue  # keyword itself is also duplicate — skip entirely
                _used_id_answers.add(precise_answer.lower())

                question = {
                    'question_text': question_text,
                    'question_type': 'identification',
                    'difficulty_level': difficulty,
                    'correct_answer': precise_answer,
                    'points': points,
                    'bloom_level': bloom_level
                }

                qt_lower = question_text.lower()
                if precise_answer and isinstance(precise_answer, str) and precise_answer.lower() in qt_lower:
                    continue
                if len(question_text.strip()) < 20:
                    continue
                if "complete the sentence" in qt_lower or "what term completes" in qt_lower:
                    continue

                if self._add_question_if_valid(question):
                    questions.append(question)
                    logger.info(f"        ✅ Created: '{question_text[:80]}...'")

            logger.info(f"        ✅ Generated {len(questions)}/{count}")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    @staticmethod
    def _clean_equation_text(text):
        """
        Strip internal [EQUATION: ...] OMML markers and return clean expression text.
        Takes only the first logical line from the tag content.
        """
        import re as _re

        def _unwrap(m):
            inner = m.group(1).strip()
            first = _re.split(r'\n|  {2,}', inner)[0].strip()
            return first[:150] if len(first) > 150 else first

        cleaned = _re.sub(r'\[EQUATION:\s*([^\]]+)\]', _unwrap, text)
        cleaned = _re.sub(r' {2,}', ' ', cleaned).strip()
        return cleaned

    @staticmethod
    def _normalize_omml_text(eq_str):
        """
        Convert common OMML extraction artifacts to standard math notation.

        Fixes applied (in order):
          1.  "54 2"    → "54^2"    OMML superscript: number + space + single digit
          2.  "x 2"     → "x^2"    letter + space + single digit
          3.  "12 332"  → "12*332" OMML implicit mult: number + space + multi-digit
                                   (lookbehind for ^ prevents corrupting "x^2 12" → "x^2*12")
          4.  "12(x+1)" → "12*(x+1)" implicit mult: digit immediately before open paren
          5.  "n x"     → "n*x"    letter + space + letter (loop)
          6.  Collapse remaining double spaces
        """
        import re as _re

        # 1. OMML superscript: number(s) + space + SINGLE digit (not followed by another digit)
        #    e.g.  "54 2"  → "54^2",  "908 2" → "908^2"
        #    Guard: single digit must NOT be followed by another digit
        #           so  "12 332" is NOT matched here (3 is followed by 32)
        eq_str = _re.sub(r'(\d+)\s+(\d)(?!\d)', r'\1^\2', eq_str)

        # 2. Letter + space + single digit → exponent  (original rule, handles "x 2" → "x^2")
        eq_str = _re.sub(r'([a-zA-Z])\s+(\d)(?!\d)', r'\1^\2', eq_str)

        # 3. OMML implicit multiplication: number(s) + space + MULTI-digit number
        #    e.g.  "12 332"   → "12*332",   "12 70836" → "12*70836"
        #    Negative lookbehind (?<!\^) prevents  "x^2 12" → "x^2*12" (the 2 is an exponent)
        eq_str = _re.sub(r'(?<!\^)(\d+)\s+(\d{2,})', r'\1*\2', eq_str)

        # 4. Implicit multiplication: digit immediately before open parenthesis
        #    e.g.  "12(3724)" → "12*(3724)",  "2(x+1)" → "2*(x+1)"
        eq_str = _re.sub(r'(\d)\(', r'\1*(', eq_str)

        # 5. Multiplication: letter + space + letter(s)
        #    No trailing \b so "n xy" → "n*xy" (xy is a combined variable)
        #    Loop because substitution is not reentrant for overlapping matches.
        prev = None
        while prev != eq_str:
            prev = eq_str
            eq_str = _re.sub(r'\b([a-zA-Z])\s+([a-zA-Z])', r'\1*\2', eq_str)

        # 6. Collapse remaining multiple spaces
        eq_str = _re.sub(r' {2,}', ' ', eq_str).strip()
        return eq_str

    @staticmethod
    def _is_trivial_equation(eq_str):
        """
        Return True for equations that are not worth asking about:
        1. Single variable = bare number (e.g. y = 3724)
        2. Both sides are purely numeric — answer is already given, circular
           (e.g. 10−1 = 9,  2+3 = 5,  100/4 = 25)
        """
        import re as _re
        # Rule 1: variable = bare number
        if _re.match(r'^\s*[A-Za-z]\s*=\s*[\d,\.]+\s*$', eq_str):
            return True
        # Rule 2: both sides of '=' are pure numeric expressions
        if '=' in eq_str:
            sides = eq_str.split('=', 1)
            _numeric = lambda s: bool(
                _re.match(r'^[\d\s\+\-\*\/\^\(\)\.−×÷,]+$', s.strip())
            ) and bool(_re.search(r'\d', s))
            if _numeric(sides[0]) and _numeric(sides[1]):
                return True
        return False

    @staticmethod
    def _is_valid_expression(eq_str):
        """
        Return True only when the expression has meaningful math content.
        Rejects lone symbols / operators (e.g. "≤", ">", "≥", ":") that slip
        through from broken OMML extraction.
        Rule: must contain at least 2 alphanumeric characters.
        """
        import re as _re
        return len(_re.findall(r'[a-zA-Z0-9]', eq_str)) >= 2

    # ──────────────────────────────────────────────────────────────────────
    # Math mode: detection, sentence extraction, concept extraction, tokenizer
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _detect_math_mode(text):
        """Return True when module content is primarily mathematical."""
        if not text:
            return False
        matches = ExamGenerator._MATH_INDICATOR_RE.findall(text)
        ratio = len(matches) / max(len(text), 1)
        # Also count lines starting with math operators or Greek letters
        math_start_lines = sum(
            1 for line in text.splitlines()
            if re.match(r'^\s*[=<>≤≥±∓αβγδεζηθικλμνξπρστυφχψωΩ]', line)
        )
        return ratio > ExamGenerator._MATH_MODE_THRESHOLD or math_start_lines > 5

    def _extract_math_sentences(self, text):
        """Collect equation-bearing sentences from raw text (before cleaning)."""
        from app.module_processor.content_extractor import ContentExtractor
        sentences = []
        seen = set()
        # Split on sentence-ending punctuation and newlines
        raw_sents = self._sent_tokenize(text)
        for sent in raw_sents:
            sent = sent.strip()
            if len(sent) < 10 or len(sent) > 500:
                continue
            norm = sent.lower()[:100]
            if norm in seen:
                continue
            # Keep sentences with equations or math content
            has_eq = ContentExtractor.sentence_has_equation(sent)
            has_greek = bool(re.search(r'[αβγδεζηθικλμνξπρστυφχψωΩΣ]', sent))
            has_formula = bool(re.search(r'[A-Za-z]\s*=\s*[A-Za-z0-9]', sent))
            if has_eq or has_greek or has_formula:
                # Unwrap OMML tags
                clean = ExamGenerator._clean_equation_text(sent)
                if clean and len(clean.strip()) >= 10:
                    sentences.append(clean.strip())
                    seen.add(norm)
            if len(sentences) >= 300:
                break
        return sentences

    def _extract_math_concepts(self, text):
        """Extract structured math concepts from module text."""
        from app.module_processor.content_extractor import ContentExtractor
        extractor = ContentExtractor()
        concepts = {
            'theorems': [],
            'equations': [],
            'definitions': [],
            'named_constants': [],
        }
        # Equations via content_extractor
        try:
            eq_results = extractor.detect_equations(text[:200000])
            concepts['equations'] = [
                ExamGenerator._clean_equation_text(e['equation'])
                for e in eq_results if e.get('equation')
            ][:100]
        except Exception:
            pass
        # Theorems / laws / rules
        theorem_pat = re.compile(
            r'(\b[A-Z][a-zA-Z\'\-]+(?:\s+[A-Z][a-zA-Z\'\-]+)*'
            r'\s+(?:theorem|law|rule|formula|identity|property|axiom|lemma|principle|equation))',
            re.IGNORECASE
        )
        concepts['theorems'] = list(dict.fromkeys(
            m.group(0).strip() for m in theorem_pat.finditer(text)
        ))[:50]
        # Definitions: "X is defined as" or "X = expression"
        def_pat = re.compile(
            r'([A-Za-z][A-Za-z\s]{2,40})\s+(?:is\s+defined\s+as|is\s+given\s+by|is\s+expressed\s+as|'
            r'represents|denotes|stands\s+for)\s+([^.\n]{5,120})',
            re.IGNORECASE
        )
        for m in def_pat.finditer(text):
            concepts['definitions'].append({
                'term': m.group(1).strip(),
                'definition': m.group(2).strip()
            })
            if len(concepts['definitions']) >= 50:
                break
        # Named constants
        const_pat = re.compile(
            r'\b(pi|π|euler|e\s*≈\s*2\.71|gravity|g\s*=\s*9\.8|'
            r'speed\s+of\s+light|c\s*=\s*3\s*[×x]\s*10|'
            r'planck|boltzmann|avogadro)\b',
            re.IGNORECASE
        )
        concepts['named_constants'] = list(dict.fromkeys(
            m.group(0).strip() for m in const_pat.finditer(text)
        ))[:20]
        return concepts

    @staticmethod
    def _math_tokenize_equation(eq_str):
        """Parse an equation string into categorized tokens."""
        eq_str = ExamGenerator._normalize_omml_text(eq_str)
        tokens = {
            'numbers':   re.findall(r'(?<![a-zA-Z])\d+(?:\.\d+)?(?![a-zA-Z])', eq_str),
            'variables': re.findall(r'\b([A-Za-z](?:_[A-Za-z0-9])?)\b', eq_str),
            'operators': re.findall(r'[+\-*/^=]', eq_str),
            'functions': re.findall(r'\b(sin|cos|tan|log|ln|exp|sqrt|lim|sum|prod)\b', eq_str, re.IGNORECASE),
            'greek':     re.findall(r'[αβγδεζηθικλμνξπρστυφχψωσΩΣ]', eq_str),
        }
        # Deduplicate while preserving order
        for key in tokens:
            seen = set()
            tokens[key] = [x for x in tokens[key] if not (x in seen or seen.add(x))]
        return tokens

    @staticmethod
    def _detect_pearson_formula(question_text, raw_eq):
        """
        Return True when the question / expression looks like the
        Pearson correlation-coefficient formula:
            r = (n·Σxy − Σx·Σy) / √[(n·Σx² − (Σx)²)(n·Σy² − (Σy)²)]
        """
        import re as _re
        combined = (question_text + ' ' + raw_eq).lower()
        # Explicit keyword match
        if any(kw in combined for kw in
               ['pearson', 'correlation coefficient', 'correlation']):
            return True
        # Structural pattern: n  +  xy product  +  x²  +  y²
        has_n    = bool(_re.search(r'\bn\b', raw_eq, _re.IGNORECASE))
        has_xy   = bool(_re.search(r'\bxy\b', raw_eq, _re.IGNORECASE))
        has_xsq  = bool(_re.search(r'x[\^]?2|x\s+2', raw_eq, _re.IGNORECASE))
        has_ysq  = bool(_re.search(r'y[\^]?2|y\s+2', raw_eq, _re.IGNORECASE))
        return has_n and has_xy and has_xsq and has_ysq

    @staticmethod
    def _build_pearson_solution(difficulty='medium'):
        """
        Return a Pearson correct answer with real randomly generated data.
        Delegates to _generate_pearson_question so every call produces
        unique numbers and a fully computed r value.
        """
        return ExamGenerator._generate_pearson_question(difficulty)['correct_answer']

    @staticmethod
    def _generate_pearson_question(difficulty='medium'):
        """
        Generate a Pearson correlation question with real random data and a
        fully computed correct answer.

        Returns a dict: {'question_text': str, 'correct_answer': str}
        """
        import random as _rnd
        import math   as _math

        _n_map     = {'easy': 4, 'medium': 5, 'hard': 6}
        _range_map = {'easy': (1, 8), 'medium': (1, 12), 'hard': (2, 15)}
        n        = _n_map.get(difficulty, 5)
        lo, hi   = _range_map.get(difficulty, (1, 12))

        # Retry loop — regenerate until denominator is non-zero
        for _attempt in range(20):
            x_vals = [_rnd.randint(lo, hi) for _ in range(n)]
            y_vals = [_rnd.randint(lo, hi) for _ in range(n)]
            sum_x  = sum(x_vals)
            sum_y  = sum(y_vals)
            sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
            sum_x2 = sum(x ** 2 for x in x_vals)
            sum_y2 = sum(y ** 2 for y in y_vals)
            left_br  = n * sum_x2 - sum_x ** 2
            right_br = n * sum_y2 - sum_y ** 2
            if left_br > 0 and right_br > 0:
                break
        else:
            # Guaranteed fallback dataset
            x_vals   = [1, 2, 3, 4, 5, 6][:n]
            y_vals   = [2, 4, 5, 4, 5, 7][:n]
            sum_x    = sum(x_vals)
            sum_y    = sum(y_vals)
            sum_xy   = sum(x * y for x, y in zip(x_vals, y_vals))
            sum_x2   = sum(x ** 2 for x in x_vals)
            sum_y2   = sum(y ** 2 for y in y_vals)
            left_br  = n * sum_x2 - sum_x ** 2
            right_br = n * sum_y2 - sum_y ** 2

        numerator   = n * sum_xy - sum_x * sum_y
        denom_sq    = left_br * right_br
        denominator = _math.sqrt(denom_sq)
        r           = numerator / denominator
        r_rounded   = round(r, 4)

        # Interpretation
        abs_r = abs(r_rounded)
        sign  = "positive" if r_rounded >= 0 else "negative"
        if abs_r >= 0.90:
            interp = f"Very strong {sign} correlation"
        elif abs_r >= 0.70:
            interp = f"Strong {sign} correlation"
        elif abs_r >= 0.40:
            interp = f"Moderate {sign} correlation"
        elif abs_r >= 0.10:
            interp = f"Weak {sign} correlation"
        else:
            interp = "No correlation (negligible)"

        H  = "=" * 60
        SH = "─" * 60

        pairs_str = "  ".join(f"({x},{y})" for x, y in zip(x_vals, y_vals))
        x_str     = ", ".join(str(v) for v in x_vals)
        y_str     = ", ".join(str(v) for v in y_vals)

        q_text = (
            f"Given the following {n} data pairs, compute the Pearson "
            f"correlation coefficient (r). Show a complete step-by-step solution.\n\n"
            f"  x: {x_str}\n"
            f"  y: {y_str}"
        )

        table_rows = "\n".join(
            f"  | {x:>3} | {y:>3} | {x*y:>5} | {x**2:>4} | {y**2:>4} |"
            for x, y in zip(x_vals, y_vals)
        )

        correct_answer = (
            f"Pearson Correlation Coefficient\n"
            f"{H}\n"
            f"Formula:\n\n"
            f"          n·Σxy − Σx·Σy\n"
            f"  r = ──────────────────────────────────────────\n"
            f"       √[ (n·Σx² − (Σx)²) · (n·Σy² − (Σy)²) ]\n\n"
            f"{H}\n"
            f"DATA   n = {n}\n"
            f"{SH}\n"
            f"  Pairs: {pairs_str}\n\n"
            f"STEP 1 — Computation Table\n"
            f"{SH}\n"
            f"  |   x |   y |    xy |  x² |  y² |\n"
            f"  |-----|-----|-------|-----|-----|\n"
            f"{table_rows}\n"
            f"  |-----|-----|-------|-----|-----|\n"
            f"  | Σx={sum_x} | Σy={sum_y} | Σxy={sum_xy} | Σx²={sum_x2} | Σy²={sum_y2} |\n\n"
            f"STEP 2 — Numerator\n"
            f"{SH}\n"
            f"  n·Σxy − Σx·Σy\n"
            f"  = {n}({sum_xy}) − ({sum_x})({sum_y})\n"
            f"  = {n * sum_xy} − {sum_x * sum_y}\n"
            f"  = {numerator}\n\n"
            f"STEP 3 — Denominator\n"
            f"{SH}\n"
            f"  Left  bracket: n·Σx² − (Σx)²\n"
            f"    = {n}({sum_x2}) − ({sum_x})²\n"
            f"    = {n * sum_x2} − {sum_x ** 2}\n"
            f"    = {left_br}\n\n"
            f"  Right bracket: n·Σy² − (Σy)²\n"
            f"    = {n}({sum_y2}) − ({sum_y})²\n"
            f"    = {n * sum_y2} − {sum_y ** 2}\n"
            f"    = {right_br}\n\n"
            f"  Denominator = √({left_br} × {right_br})\n"
            f"             = √{denom_sq}\n"
            f"             = {round(denominator, 4)}\n\n"
            f"STEP 4 — Divide\n"
            f"{SH}\n"
            f"  r = {numerator} ÷ {round(denominator, 4)}\n"
            f"  r = {r_rounded}\n\n"
            f"STEP 5 — Interpret\n"
            f"{SH}\n"
            f"  r = {r_rounded}  →  {interp}\n\n"
            f"{H}\n"
            f"Final Answer:  r = {r_rounded}\n\n"
            f"Verification:  r must be in [−1, +1].\n"
            f"               If outside this range, recheck all column sums."
        )

        return {'question_text': q_text, 'correct_answer': correct_answer}

    @staticmethod
    def _generate_hypothesis_testing_question(difficulty='medium'):
        """
        Generate a one-sample z-test problem with random data and a fully
        computed step-by-step solution.  Uses numpy + scipy.stats.
        """
        import math as _math
        try:
            import numpy as _np
            from scipy import stats as _stats
        except ImportError:
            return None

        mu    = round(random.uniform(60, 85), 1)
        sigma = round(random.uniform(5, 15), 1)
        n     = random.choice([25, 36, 49, 64, 100])
        x_bar = round(mu + random.uniform(-4, 4), 2)
        alpha = random.choice([0.01, 0.05, 0.10])

        se     = sigma / _np.sqrt(n)
        z      = round((x_bar - mu) / se, 4)
        z_crit = round(float(_stats.norm.ppf(1 - alpha / 2)), 4)
        reject = abs(z) > z_crit
        decision = "Reject H\u2080" if reject else "Fail to reject H\u2080"

        q_text = (
            f"A population has a known standard deviation of \u03c3 = {sigma}. "
            f"A random sample of n = {n} gives a sample mean of x\u0305 = {x_bar}. "
            f"Test H\u2080: \u03bc = {mu} vs H\u2081: \u03bc \u2260 {mu} at \u03b1 = {alpha}. "
            f"Compute the z-statistic and state your decision."
        )

        H  = "=" * 60
        SH = "\u2500" * 60
        solution = (
            f"One-Sample Z-Test Solution\n{H}\n"
            f"Given:  \u03bc\u2080 = {mu},  \u03c3 = {sigma},  n = {n},  "
            f"x\u0305 = {x_bar},  \u03b1 = {alpha} (two-tailed)\n{H}\n\n"
            f"STEP 1 \u2014 Standard Error\n{SH}\n"
            f"  SE = \u03c3 / \u221an = {sigma} / \u221a{n} = {round(se, 4)}\n\n"
            f"STEP 2 \u2014 z-Statistic\n{SH}\n"
            f"  z = (x\u0305 - \u03bc\u2080) / SE = ({x_bar} - {mu}) / {round(se, 4)} = {z}\n\n"
            f"STEP 3 \u2014 Critical Value\n{SH}\n"
            f"  z_\u03b1/2 = \u00b1{z_crit}  (for \u03b1 = {alpha}, two-tailed test)\n\n"
            f"STEP 4 \u2014 Decision\n{SH}\n"
            f"  |z| = {abs(z)}  {'>' if reject else '≤'}  z_\u03b1/2 = {z_crit}\n"
            f"  \u2192 {decision}\n\n"
            f"{H}\n"
            f"Final Answer:  z = {z};  {decision}"
        )
        return {
            'question_text':  q_text,
            'correct_answer': solution,
            'numeric_value':  z,
            'difficulty':     difficulty,
        }

    @staticmethod
    def _build_ps_solution(question_text, difficulty='medium'):
        """
        Build an expert-level mathematical normalization and solution guide.

        Four formal sections (matching the Expert-Level Mathematical Normalization prompt):
          I.  Lexical Normalization
          II. Structural Verification
          III.Algebraic Simplification
          IV. Final Statement  →  Final Answer:
        """
        import re as _re

        H  = "=" * 60
        SH = "─" * 60

        # ── 0. Strip [EQUATION: ...] wrapper ─────────────────────────────────
        question_text = ExamGenerator._clean_equation_text(question_text)

        # ── 1. Extract the core expression from the question text ─────────────
        # Strategy: find everything after the LAST colon in the question text.
        # This handles chained keyword phrases like
        # "Calculate the result of the following expression: <expr>"
        # without accidentally capturing "expression:" as part of the expression.
        colon_idx = question_text.rfind(':')
        if colon_idx != -1:
            candidate = question_text[colon_idx + 1:].strip().rstrip('.').strip()
            # Only use the colon-split result if it contains actual math content
            if ExamGenerator._is_valid_expression(candidate):
                raw_eq = candidate
            else:
                raw_eq = question_text          # fallback: use full text
        else:
            # No colon: try the keyword-regex approach
            eq_match = _re.search(
                r'(?:equation[:\s]+|expression[:\s]+|following[:\s]+|of[:\s]+|given[:\s]+)'
                r'([^\.\?]+)',
                question_text, _re.IGNORECASE
            )
            raw_eq = eq_match.group(1).strip().rstrip('.').strip() if eq_match else question_text

        # ── 1b. Pearson correlation coefficient — early exit ──────────────────
        if ExamGenerator._detect_pearson_formula(question_text, raw_eq):
            return ExamGenerator._build_pearson_solution(difficulty)

        # ── 1c. Attempt SymPy computation ─────────────────────────────────────
        _sympy_result = None
        try:
            from app.exam.math_solver import try_sympy_solve
            _sr = try_sympy_solve(raw_eq)
            if _sr.get('success') and _sr.get('numeric_value') is not None:
                _sympy_result = round(_sr['numeric_value'], 4)
        except Exception:
            pass

        # ── 2. Normalize OMML artifacts → strict algebraic notation ──────────
        norm_eq = ExamGenerator._normalize_omml_text(raw_eq)

        # Detect expression type
        eq_lower    = norm_eq.lower()
        has_equals  = '=' in norm_eq
        is_calculus = any(s in eq_lower for s in
                          ['∫', 'd/dx', 'dy/dx', '∂', 'lim', '∑', 'integral',
                           'sigma', 'derivative'])
        is_trig_log = any(s in eq_lower for s in
                          ['sin', 'cos', 'tan', 'log', 'ln', 'sqrt', '√', 'exp'])

        # ── 3. Build solution steps ───────────────────────────────────────────
        if has_equals:
            lhs   = norm_eq.split('=')[0].strip()
            var_m = _re.search(r'\b([A-Za-z])\b', lhs)
            var   = var_m.group(1) if var_m else lhs
            simp_steps = (
                f"Step 1 — Isolate {var} using inverse operations\n"
                f"         (undo +/− first, then ×/÷, then exponents).\n"
                f"Step 2 — Combine like terms on each side.\n"
                f"Step 3 — Show each arithmetic operation on its own line."
            )
            if _sympy_result is not None:
                final_label = f"Final Answer: {var} = {_sympy_result}"
                verify_note = f"Verification: substituting {var} = {_sympy_result} into {norm_eq} confirms the result."
            else:
                final_label = f"Final Answer: {var} = _____ (show computed value)"
                verify_note = f"Verification: substitute the result back into {norm_eq} and confirm both sides are equal."
        elif is_calculus:
            simp_steps = (
                f"Step 1 — Identify the operation (integral / derivative / limit).\n"
                f"Step 2 — Apply the relevant rule (Power Rule, Chain Rule, FTC, etc.).\n"
                f"Step 3 — Simplify term by term; apply boundary conditions if needed."
            )
            final_label = (f"Final Answer: {_sympy_result}"
                           if _sympy_result is not None
                           else "Final Answer: _____ (express in correct mathematical notation)")
            verify_note = (f"Verification: computed value = {_sympy_result}."
                           if _sympy_result is not None
                           else "Verification: differentiate the result or substitute the limit value to confirm.")
        elif is_trig_log:
            simp_steps = (
                f"Step 1 — Identify all functions present (sin, cos, log, ln, √, etc.).\n"
                f"Step 2 — Substitute given values and apply the relevant identity or law.\n"
                f"Step 3 — Simplify one operation per line to reach a single value."
            )
            final_label = (f"Final Answer: {_sympy_result}"
                           if _sympy_result is not None
                           else "Final Answer: _____ (numerical or symbolic result)")
            verify_note = (f"Verification: computed value = {_sympy_result}."
                           if _sympy_result is not None
                           else "Verification: substitute the result back to confirm consistency.")
        else:
            simp_steps = (
                f"Step 1 — Follow PEMDAS/BODMAS: Parentheses → Exponents → ×÷ → +−.\n"
                f"Step 2 — Evaluate parentheses and exponents first.\n"
                f"Step 3 — Perform each remaining operation left to right, one per line."
            )
            final_label = (f"Final Answer: {_sympy_result}"
                           if _sympy_result is not None
                           else "Final Answer: _____ (fully simplified numerical value)")
            verify_note = (f"Verification: computed value = {_sympy_result}."
                           if _sympy_result is not None
                           else "Verification: re-evaluate the expression step by step to confirm.")

        # ── 4. Assemble a clean, concise answer ──────────────────────────────
        expr_line = f"Expression:  {norm_eq}" if norm_eq == raw_eq else (
            f"Expression:  {norm_eq}  (original: {raw_eq})"
        )
        return (
            f"{expr_line}\n\n"
            f"Solution:\n"
            f"{simp_steps}\n\n"
            f"{final_label}\n\n"
            f"{verify_note}"
        )

    def _generate_conceptual(self, text_content, difficulty, count, points,
                             bloom_level='understanding', module_ids=None):
        """
        DB-first conceptual question generator.
        Phase A: Pull pre-processed conceptual questions from module_questions table.
        Phase B: Generate section-based conceptual questions from headings in raw text.
        """
        logger.info(f"        📝 Generating {count} Conceptual ({difficulty})...")
        questions = []

        try:
            # Phase A — DB-first
            if module_ids:
                db_qs = self._query_module_questions(module_ids, 'conceptual', difficulty, count)
                if len(db_qs) >= count:
                    logger.info(f"        ✅ DB-first satisfied all {count} conceptual questions")
                    return db_qs
                questions.extend(db_qs)
                count -= len(db_qs)

            if count <= 0:
                return questions

            # Phase B — generate from section headings extracted from raw text
            heading_pat = re.compile(
                r'^(?:[IVX]+\.|[0-9]+\.|\*{1,2}|#{1,3})\s*(.{5,80})$',
                re.MULTILINE
            )
            headings = heading_pat.findall(text_content)
            clean_text = self._clean_text_for_questions(text_content)
            # Fall back: split on double newlines to find paragraph leads
            if not headings:
                chunks = [c.strip() for c in clean_text.split('\n\n') if len(c.strip()) > 60]
                headings = [c[:80].rstrip('.') for c in chunks[:20]]

            random.shuffle(headings)
            for heading in headings:
                if len(questions) >= count + len(questions):
                    break
                heading = heading.strip().strip('*#').strip()
                if not heading or len(heading) < 5:
                    continue

                # Extract section content for this heading (next 500 chars after heading in text)
                h_idx = text_content.find(heading)
                section_content = text_content[h_idx + len(heading): h_idx + len(heading) + 500].strip() if h_idx != -1 else ''

                # QG primary — attempt to generate a context-specific question
                q_text, answer = None, None
                try:
                    qg = self._get_question_generator()
                    if qg and section_content:
                        result = qg.generate_question(
                            context_text=section_content[:500],
                            tfidf_keyword=heading,
                            topic=heading,
                            bloom_level=bloom_level,
                            difficulty_level=difficulty,
                            question_type='short_answer',
                            points=points
                        )
                        if result and result.get('question_text') and len(result['question_text']) > 15:
                            q_text = result['question_text']
                            answer = result.get('correct_answer') or section_content[:200]
                except Exception:
                    pass

                # Template fallback
                if not q_text:
                    stem = self._pick_bloom_stem(bloom_level or 'understanding')
                    if '___' in stem:
                        q_text = stem.replace('___', heading)
                    else:
                        q_text = f"{stem} {heading}"
                    answer = section_content[:200] if section_content else '[Answer based on module content]'

                norm = self._normalize_text(q_text)
                if norm in self.generated_questions:
                    continue
                self.generated_questions.add(norm)
                questions.append({
                    'question_text':    q_text,
                    'correct_answer':   answer,
                    'question_type':    'conceptual',
                    'difficulty_level': difficulty,
                    'bloom_level':      bloom_level,
                    'topic':            heading[:100],
                    'options':          None,
                    'points':           points,
                })
                if len(questions) >= count + len(questions) - count:
                    break

            logger.info(f"        ✅ Generated {len(questions)} conceptual questions")
        except Exception as e:
            logger.error(f"        ❌ _generate_conceptual error: {e}")
        return questions

    def _generate_analysis(self, text_content, difficulty, count, points,
                           bloom_level='analyzing', module_ids=None):
        """
        DB-first analysis question generator.
        Phase A: Pull pre-processed analysis questions from module_questions table.
        Phase B: Generate evaluate/compare/analyze prompts from section headings.
        """
        logger.info(f"        📝 Generating {count} Analysis ({difficulty})...")
        questions = []

        _analysis_templates = [
            t.replace('___', '{heading}')
            for t in self.BLOOM_STEMS.get('analyzing', [])
        ]

        try:
            # Phase A — DB-first
            if module_ids:
                db_qs = self._query_module_questions(module_ids, 'analysis', difficulty, count)
                if len(db_qs) >= count:
                    logger.info(f"        ✅ DB-first satisfied all {count} analysis questions")
                    return db_qs
                questions.extend(db_qs)
                count -= len(db_qs)

            if count <= 0:
                return questions

            # Phase B — generate from section headings
            heading_pat = re.compile(
                r'^(?:[IVX]+\.|[0-9]+\.|\*{1,2}|#{1,3})\s*(.{5,80})$',
                re.MULTILINE
            )
            headings = heading_pat.findall(text_content)
            clean_text = self._clean_text_for_questions(text_content)
            if not headings:
                chunks = [c.strip() for c in clean_text.split('\n\n') if len(c.strip()) > 60]
                headings = [c[:80].rstrip('.') for c in chunks[:20]]

            random.shuffle(headings)
            needed = count
            for heading in headings:
                if len(questions) - (count - needed) >= needed:
                    break
                heading = heading.strip().strip('*#').strip()
                if not heading or len(heading) < 5:
                    continue

                # Extract section content for context
                h_idx = text_content.find(heading)
                section_content = text_content[h_idx + len(heading): h_idx + len(heading) + 500].strip() if h_idx != -1 else ''

                # QG primary — attempt context-specific analysis question
                q_text, answer = None, None
                try:
                    qg = self._get_question_generator()
                    if qg and section_content:
                        result = qg.generate_question(
                            context_text=section_content[:500],
                            tfidf_keyword=heading,
                            topic=heading,
                            bloom_level=bloom_level,
                            difficulty_level=difficulty,
                            question_type='short_answer',
                            points=points
                        )
                        if result and result.get('question_text') and len(result['question_text']) > 15:
                            q_text = result['question_text']
                            answer = result.get('correct_answer') or section_content[:200]
                except Exception:
                    pass

                # Template fallback
                if not q_text:
                    if _analysis_templates:
                        template = random.choice(_analysis_templates)
                        q_text = template.format(heading=heading)
                    else:
                        q_text = f"Analyze the significance of '{heading}'."
                    answer = section_content[:200] if section_content else '[Analysis based on module content]'

                norm = self._normalize_text(q_text)
                if norm in self.generated_questions:
                    continue
                self.generated_questions.add(norm)
                questions.append({
                    'question_text':    q_text,
                    'correct_answer':   answer,
                    'question_type':    'analysis',
                    'difficulty_level': difficulty,
                    'bloom_level':      bloom_level,
                    'topic':            heading[:100],
                    'options':          None,
                    'points':           points,
                })

            logger.info(f"        ✅ Generated {len(questions)} analysis questions")
        except Exception as e:
            logger.error(f"        ❌ _generate_analysis error: {e}")
        return questions

    def _generate_problem_solving(self, text_content, difficulty, count, points, module_ids=None):
        """
        Generates problem-solving / computation questions.

        Priority order:
          Phase A (DB-first): Pull pre-processed problem_solving questions from the
                              module_questions table for the given module_ids.
                              These are linked back via _module_question_id so
                              ExamQuestion.module_question_id is populated.
          Phase B (equations): Scan raw text for embedded equations and generate
                              computation questions from those.
          Phase C (keyword fallback): If still short, generate from TF-IDF keywords.

        Rules:
        - NO blanks in the question text — the equation/expression IS the problem.
        - correct_answer contains a FULL step-by-step solution guide (not just a final value).
        - Bloom's level is fixed per difficulty:
            easy   → applying   (apply a formula or perform straightforward computation)
            medium → analyzing  (multi-step analysis / structured solving)
            hard   → evaluating (evaluate complex or calculus-level expressions)
        """
        logger.info(f"        📝 Generating {count} Problem-Solving ({difficulty}, "
                    f"module_ids={module_ids})...")

        # Dedicated Bloom's map — independent of the global BLOOM_MAP
        PS_BLOOM_MAP = {'easy': 'applying', 'medium': 'analyzing', 'hard': 'evaluating'}
        bloom = PS_BLOOM_MAP.get(difficulty, 'applying')

        questions = []

        try:
            from app.module_processor.content_extractor import ContentExtractor
            extractor = ContentExtractor()

            # ── Phase A (DB-first): Pull stored problem_solving questions ─────
            # Query the module_questions table that was populated by the module
            # processor (saved_module.py).  This is the primary source — NLP
            # generation is only the fallback when the DB has fewer questions
            # than requested.
            if module_ids:
                try:
                    from app.module_processor.models import ModuleQuestion
                    db_qs = (
                        ModuleQuestion.query
                        .filter(
                            ModuleQuestion.module_id.in_(module_ids),
                            ModuleQuestion.question_type == 'problem_solving',
                            ModuleQuestion.difficulty_level == difficulty,
                        )
                        .order_by(ModuleQuestion.created_at.desc())
                        .limit(count * 4)
                        .all()
                    )

                    # If no exact-difficulty match, accept any difficulty
                    if not db_qs:
                        db_qs = (
                            ModuleQuestion.query
                            .filter(
                                ModuleQuestion.module_id.in_(module_ids),
                                ModuleQuestion.question_type == 'problem_solving',
                            )
                            .order_by(ModuleQuestion.created_at.desc())
                            .limit(count * 4)
                            .all()
                        )

                    random.shuffle(db_qs)
                    logger.info(
                        f"        🗄️  DB found {len(db_qs)} stored problem_solving "
                        f"questions for modules {module_ids}"
                    )

                    for mq in db_qs:
                        if len(questions) >= count:
                            break

                        # ── Quality gates ────────────────────────────────────
                        # 1. No blank markers in stored question text
                        if '______' in mq.question_text:
                            continue

                        # 2. Strip [EQUATION: ...] OMML wrappers and fix spaced
                        #    characters from PDF extraction artifacts
                        clean_q_text = ExamGenerator._fix_spaced_characters(
                            ExamGenerator._clean_equation_text(mq.question_text)
                        )

                        # 3. Extract the embedded equation, then validate and filter
                        import re as _re_q
                        # Use last-colon extraction (same logic as _build_ps_solution)
                        _colon = clean_q_text.rfind(':')
                        if _colon != -1:
                            _raw_eq = clean_q_text[_colon + 1:].strip().rstrip('.')
                        else:
                            _m = _re_q.search(
                                r'(?:equation|expression|of|given)[:\s]+([^\.\?]+)',
                                clean_q_text, _re_q.IGNORECASE
                            )
                            _raw_eq = _m.group(1).strip().rstrip('.') if _m else ''

                        if _raw_eq:
                            # Skip degenerate expressions (lone symbols like "≤")
                            if not ExamGenerator._is_valid_expression(_raw_eq):
                                logger.info(
                                    f"        ⏭️  Skipping degenerate DB expression: "
                                    f"'{_raw_eq}'"
                                )
                                continue
                            # Skip trivial "variable = bare-number" (e.g. y = 3724)
                            if ExamGenerator._is_trivial_equation(_raw_eq):
                                logger.info(
                                    f"        ⏭️  Skipping trivial DB equation: "
                                    f"'{_raw_eq}'"
                                )
                                continue

                        # Pearson correlation: replace question with real-data version
                        if ExamGenerator._detect_pearson_formula(clean_q_text,
                                                                  _raw_eq or ''):
                            if self._pearson_generated:
                                logger.info(
                                    "        ⏭️  Skipping duplicate Pearson question"
                                )
                                continue
                            _pq                    = ExamGenerator._generate_pearson_question(
                                difficulty
                            )
                            clean_q_text           = _pq['question_text']
                            solution               = _pq['correct_answer']
                            self._pearson_generated = True
                        else:
                            solution = ExamGenerator._build_ps_solution(
                                clean_q_text, difficulty
                            )
                        question = {
                            'question_text': clean_q_text,
                            'question_type': 'problem_solving',
                            # Use the REQUESTED difficulty, not the stored one
                            # (teacher chose hard, so tag the question as hard)
                            'difficulty_level': difficulty,
                            'correct_answer': solution,
                            'points': points,
                            'bloom_level': bloom,
                            'topic': mq.topic or 'Computation',
                            # Links ExamQuestion.module_question_id → module_questions.question_id
                            '_module_question_id': mq.question_id,
                            # Propagate image link so ExamQuestion.image_id is set
                            '_image_id': mq.image_id,
                        }
                        if self._add_question_if_valid(question):
                            questions.append(question)
                            logger.info(
                                f"        🗄️  DB Q (id={mq.question_id}): "
                                f"'{clean_q_text[:70]}...'"
                            )

                except Exception as db_err:
                    logger.warning(
                        f"        ⚠️  DB pull failed ({db_err}); falling back to NLP"
                    )

            # ── Phase B: equation-based NLP questions (if DB didn't fill quota) ──
            sentences = [s for s in self._sent_tokenize(text_content)
                         if 10 < len(s) < 500]

            seen_equations = set()

            for sent in sentences:
                if len(questions) >= count:
                    break
                if not ContentExtractor.sentence_has_equation(sent):
                    continue

                detected = extractor.detect_equations(sent)
                if not detected:
                    continue

                for eq_info in detected:
                    if len(questions) >= count:
                        break

                    eq_str = eq_info.get('equation', '').strip()
                    if not eq_str or eq_str in seen_equations:
                        continue

                    # Strip [EQUATION: ...] wrapper (DOCX OMML internal tag)
                    eq_str = ExamGenerator._clean_equation_text(eq_str)

                    # Skip expressions with no meaningful math content
                    # e.g. lone symbols/operators: "≤", "≥", ":", ">" from broken OMML
                    if not ExamGenerator._is_valid_expression(eq_str):
                        logger.info(f"        ⏭️  Skipping degenerate expression: '{eq_str}'")
                        continue

                    # Skip trivial "variable = bare number" (e.g. y = 3724)
                    if ExamGenerator._is_trivial_equation(eq_str):
                        continue

                    # Normalize OMML artifacts → clean standard notation
                    norm_eq = ExamGenerator._normalize_omml_text(eq_str)
                    seen_equations.add(norm_eq)

                    # ── Pearson correlation: replace with a real-data question ──
                    if ExamGenerator._detect_pearson_formula('', norm_eq):
                        if self._pearson_generated:
                            logger.info(
                                "        ⏭️  Skipping duplicate Pearson question"
                            )
                            continue
                        _pq                    = ExamGenerator._generate_pearson_question(difficulty)
                        q_text                 = _pq['question_text']
                        solution               = _pq['correct_answer']
                        self._pearson_generated = True
                    else:
                        eq_lower = norm_eq.lower()
                        has_equals  = '=' in norm_eq
                        is_calculus = any(sym in eq_lower for sym in
                                          ['integral', '∫', 'd/dx', 'dy/dx', '∂', 'lim',
                                           '∑', 'sigma', 'matrix', 'determinant'])
                        is_trig_log = any(sym in eq_lower for sym in
                                          ['sin', 'cos', 'tan', 'log', 'ln', 'sqrt', '√',
                                           'exp'])

                        # ── Build question text (no blanks, normalized eq) ────
                        if has_equals:
                            lhs = norm_eq.split('=')[0].strip()
                            var_match = re.search(r'\b([A-Za-z])\b', lhs)
                            var = var_match.group(1) if var_match else lhs
                            q_templates = [
                                f"Solve for {var} in the equation: {norm_eq}. "
                                f"Show the complete step-by-step solution.",
                                f"Given the equation {norm_eq}, find the value of {var}. "
                                f"Show all computations.",
                                f"Determine {var} from: {norm_eq}. "
                                f"Provide a full worked solution.",
                            ]
                        elif is_calculus:
                            q_templates = [
                                f"Evaluate the following expression and show all steps: {norm_eq}",
                                f"Compute the result of: {norm_eq}. Provide a complete worked solution.",
                                f"Solve the following: {norm_eq}. Show all intermediate steps.",
                            ]
                        elif is_trig_log:
                            q_templates = [
                                f"Evaluate the expression: {norm_eq}. Show complete computations.",
                                f"Calculate the value of: {norm_eq}. Provide a full worked solution.",
                                f"Compute: {norm_eq}. Show every step of your solution.",
                            ]
                        else:
                            q_templates = [
                                f"Calculate the result of the following expression: {norm_eq}. "
                                f"Show all steps.",
                                f"Evaluate: {norm_eq}. Provide a complete computation.",
                                f"Compute the value of: {norm_eq}. Show your full working.",
                            ]

                        q_text   = random.choice(q_templates)
                        solution = ExamGenerator._build_ps_solution(q_text, difficulty)

                    question = {
                        'question_text': q_text,
                        'question_type': 'problem_solving',
                        'difficulty_level': difficulty,
                        'correct_answer': solution,
                        'points': points,
                        'bloom_level': bloom,
                    }
                    if self._add_question_if_valid(question):
                        questions.append(question)
                        logger.info(f"        🧮 NLP Equation Q: '{q_text[:70]}...'")

            # ── Phase C: Statistics problem generator (hypothesis testing) ──────
            # If content is statistics-related and we still need questions, generate
            # real z-test / hypothesis testing problems with computed answers.
            _STATS_KEYWORDS = {
                'hypothesis', 'z-test', 't-test', 'mean', 'sigma', 'population',
                'sample', 'null hypothesis', 'significance', 'p-value', 'alpha',
                'standard deviation', 'confidence interval', 'normal distribution',
            }
            content_lower = text_content.lower()
            is_stats_module = any(kw in content_lower for kw in _STATS_KEYWORDS)

            if len(questions) < count and is_stats_module:
                needed = count - len(questions)
                logger.info(
                    f"        📊 Statistics module detected — generating {needed} "
                    f"hypothesis testing problem(s)"
                )
                for _ in range(needed * 2):  # generate extras to account for dedup
                    if len(questions) >= count:
                        break
                    try:
                        ht_q = ExamGenerator._generate_hypothesis_testing_question(difficulty)
                        if not ht_q:
                            continue
                        question = {
                            'question_text':  ht_q['question_text'],
                            'question_type':  'problem_solving',
                            'difficulty_level': difficulty,
                            'correct_answer': ht_q['correct_answer'],
                            'points':         points,
                            'bloom_level':    bloom,
                            'topic':          'Hypothesis Testing',
                        }
                        if self._add_question_if_valid(question):
                            questions.append(question)
                            _ht_preview = ht_q['question_text'][:70]
                            logger.info(f"        📊 HT Q: '{_ht_preview}...'")
                    except Exception as ht_err:
                        logger.warning(f"        ⚠️  HT generator error: {ht_err}")
                        break

            if len(questions) < count:
                logger.info(
                    f"        ℹ️  Only {len(questions)}/{count} problem-solving questions "
                    f"available. Keyword fallback skipped (requires real equations)."
                )

            logger.info(f"        ✅ Generated {len(questions)}/{count} problem-solving questions")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error in _generate_problem_solving: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    # ======================================================================
    # MATH MODE GENERATORS
    # ======================================================================

    def _math_compute_distractors(self, correct_value, difficulty):
        """
        Generate pedagogically sound wrong answers for numeric MCQs.

        Easy:   simple arithmetic errors (+-1, *2)
        Medium: sign errors, doubling, reciprocal
        Hard:   reciprocal, sqrt, square, rounding error
        """
        import math as _math

        v = float(correct_value)
        dp = len(str(correct_value).split('.')[-1]) if '.' in str(correct_value) else 0

        def _fmt(x):
            r = round(x, max(dp, 2))
            if r == 0:
                r = 0   # normalise -0.0 → 0
            s = str(r)
            if '.' in s:
                s = s.rstrip('0').rstrip('.')
            return s

        correct_str = _fmt(v)

        if difficulty == 'easy':
            raw = [v + 1, v - 1, v * 2]
        elif difficulty == 'medium':
            raw = [-v, v + v]
            if v != 0:
                raw.append(round(1 / v, 4))
            raw.append(v * v if abs(v) < 100 else v / 2)
        else:
            raw = [-v, round(v * 1.1, max(dp, 2))]
            if v >= 0:
                raw.append(round(_math.sqrt(abs(v)), 2))
            if abs(v) <= 10:
                raw.append(v ** 2)
            else:
                raw.append(v / 2)

        seen = {correct_str}
        result = []
        for c in raw:
            try:
                s = _fmt(c)
                if s not in seen and s not in ('nan', 'inf', '-inf'):
                    seen.add(s)
                    result.append(s)
            except Exception:
                continue

        # Pad to 3 with simple fallbacks
        for p in [_fmt(v + 2), _fmt(v - 2), _fmt(v * 3), _fmt(abs(v) + 0.5)]:
            if len(result) >= 3:
                break
            if p not in seen:
                seen.add(p)
                result.append(p)

        return result[:3]

    def _math_generate_mcq(self, text_content, difficulty, count, points,
                            bloom_level='remembering', module_ids=None):
        """Generate MCQs from math/equation content with SymPy-verified answers."""
        from app.exam.math_solver import compute_missing_value, try_sympy_solve

        questions = []
        try:
            # Phase A: DB-first (unchanged)
            if module_ids:
                db_qs = self._query_module_questions(
                    module_ids, ['factual', 'conceptual', 'problem_solving'],
                    difficulty, count * 4, target_type='multiple_choice', points=points
                )
                for q in db_qs:
                    if len(questions) >= count:
                        break
                    ans = (q.get('correct_answer') or '').strip()
                    if not ans or len(ans.split()) > 8:
                        continue
                    other_answers = [
                        dq.get('correct_answer', '').strip() for dq in db_qs
                        if dq.get('correct_answer', '').strip() != ans
                        and dq.get('correct_answer', '').strip()
                    ]
                    distractors = list(dict.fromkeys(other_answers))[:3]
                    if len(distractors) < 3:
                        continue
                    q['options'] = [ans] + distractors
                    random.shuffle(q['options'])
                    q['question_type'] = 'multiple_choice'
                    q['bloom_level'] = bloom_level or 'remembering'
                    q['points'] = points
                    if self._add_question_if_valid(q):
                        questions.append(q)

            # Phase B: SymPy-verified equation MCQs
            math_sents = getattr(self, '_math_sentences', [])
            math_concepts = getattr(self, '_math_concepts', {})
            all_equations = math_concepts.get('equations', [])

            # Strategy B1: Blank-and-verify (all difficulties)
            for sent in math_sents:
                if len(questions) >= count:
                    break
                tokens = ExamGenerator._math_tokenize_equation(sent)
                blank_pool = []
                for num in tokens['numbers']:
                    if len(num) >= 1 and num not in ('0', '1'):
                        blank_pool.append(('number', num))
                for var in tokens['variables']:
                    if len(var) == 1 and var.lower() not in ('a', 'i'):
                        blank_pool.append(('variable', var))
                for gr in tokens['greek']:
                    blank_pool.append(('greek', gr))

                if not blank_pool:
                    continue

                target_type, target = random.choice(blank_pool)
                blanked = sent.replace(target, '_______', 1)
                if blanked == sent:
                    continue

                # SymPy verification: solve for the blanked token
                verified_val = compute_missing_value(sent, target) if '=' in sent else None

                if verified_val is not None and target_type == 'number':
                    # SymPy-verified answer
                    correct_str = str(round(verified_val, 4))
                    if '.' in correct_str:
                        correct_str = correct_str.rstrip('0').rstrip('.')
                    stem = f"What is the value of _______ in the expression:\n{blanked}"
                    distractors = self._math_compute_distractors(verified_val, difficulty)
                else:
                    # Fallback to original token
                    correct_str = target
                    stem = f"In the expression: {blanked}\nWhat value or symbol fills the blank?"
                    distractors = []
                    if target_type == 'number':
                        try:
                            val = float(target)
                            distractors = self._math_compute_distractors(val, difficulty)
                        except ValueError:
                            pass
                    elif target_type == 'variable':
                        all_vars = set()
                        for eq in all_equations[:20]:
                            t = ExamGenerator._math_tokenize_equation(eq)
                            all_vars.update(t['variables'])
                        all_vars.discard(target)
                        distractors = list(all_vars)[:3]
                    elif target_type == 'greek':
                        greek_pool = list('αβγδεζηθλμνπρστφχψω')
                        distractors = [g for g in greek_pool if g != target]
                        random.shuffle(distractors)
                        distractors = distractors[:3]

                # Pad distractors if needed
                if len(distractors) < 3:
                    generic = ['0', '1', '2', 'n', 'x', 'π', 'e']
                    for g in generic:
                        if g != correct_str and g not in distractors:
                            distractors.append(g)
                        if len(distractors) >= 3:
                            break

                if len(distractors) < 3:
                    continue

                options = [correct_str] + distractors[:3]
                random.shuffle(options)

                q = {
                    'question_text': stem,
                    'correct_answer': correct_str,
                    'question_type': 'multiple_choice',
                    'difficulty_level': difficulty,
                    'bloom_level': bloom_level or 'remembering',
                    'topic': 'Mathematics',
                    'options': options,
                    'points': points,
                }
                if self._add_question_if_valid(q):
                    questions.append(q)

            # Strategy B2: Solve-for-X MCQ (medium/hard only)
            if len(questions) < count and difficulty in ('medium', 'hard'):
                for eq in all_equations:
                    if len(questions) >= count:
                        break
                    if ExamGenerator._is_trivial_equation(eq):
                        continue
                    result = try_sympy_solve(eq)
                    if not (result.get('success') and result.get('numeric_value') is not None):
                        continue
                    numeric_val = result['numeric_value']
                    # Extract variable name
                    var_name = 'x'
                    expr_str = result.get('sympy_expr', '')
                    var_match = re.match(r'([A-Za-z_]\w*)\s*=', expr_str)
                    if var_match:
                        var_name = var_match.group(1)
                    correct_str = str(round(numeric_val, 4))
                    if '.' in correct_str:
                        correct_str = correct_str.rstrip('0').rstrip('.')
                    distractors = self._math_compute_distractors(numeric_val, difficulty)
                    if len(distractors) < 3:
                        continue
                    options = [correct_str] + distractors[:3]
                    random.shuffle(options)
                    stem = f"Solve for {var_name} in the equation:\n{eq}"
                    q = {
                        'question_text': stem,
                        'correct_answer': correct_str,
                        'question_type': 'multiple_choice',
                        'difficulty_level': difficulty,
                        'bloom_level': bloom_level or 'applying',
                        'topic': 'Mathematics',
                        'options': options,
                        'points': points,
                    }
                    if self._add_question_if_valid(q):
                        questions.append(q)

            logger.info(f"        🔢 Math MCQ: generated {len(questions)}/{count}")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error in _math_generate_mcq: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return questions

    def _math_generate_true_false(self, text_content, difficulty, count, points,
                                   bloom_level='remembering', module_ids=None):
        """Generate T/F questions from math/equation content with SymPy verification."""
        from app.exam.math_solver import verify_equation_holds, verify_mutation_is_false

        questions = []
        try:
            # Phase A: DB-first (unchanged)
            if module_ids:
                db_qs = self._query_module_questions(
                    module_ids, None, difficulty, count * 4,
                    target_type='true_false', points=points
                )
                for q in db_qs:
                    if len(questions) >= count:
                        break
                    ans = (q.get('correct_answer') or '').strip()
                    q_text = q.get('question_text', '')
                    if ans and len(ans.split()) <= 15:
                        stmt = q_text if '?' not in q_text else f"{q_text.split('?')[0].strip()} is {ans}"
                        q['question_text'] = stmt
                        q['correct_answer'] = 'True'
                        q['question_type'] = 'true_false'
                        q['bloom_level'] = bloom_level or 'remembering'
                        q['points'] = points
                        q['options'] = None
                        if self._add_question_if_valid(q):
                            questions.append(q)

            # Phase B: SymPy-verified formula T/F
            math_sents = getattr(self, '_math_sentences', [])
            math_concepts = getattr(self, '_math_concepts', {})
            remaining = count - len(questions)
            true_budget = max(1, (remaining + 1) // 2)
            false_budget = max(1, remaining - true_budget)
            true_count = 0
            false_count = 0

            # Strategy B1+B2: Equation-based T/F with SymPy gating
            for sent in math_sents:
                if len(questions) >= count:
                    break

                # TRUE: only emit if SymPy verifies or sentence has no equality claim
                if true_count < true_budget:
                    has_eq = '=' in sent
                    if has_eq:
                        # SymPy gate: verify the equation is actually correct
                        if verify_equation_holds(sent):
                            q_true = {
                                'question_text': sent,
                                'correct_answer': 'True',
                                'question_type': 'true_false',
                                'difficulty_level': difficulty,
                                'bloom_level': bloom_level or 'remembering',
                                'topic': 'Mathematics',
                                'options': None,
                                'points': points,
                            }
                            if self._add_question_if_valid(q_true):
                                questions.append(q_true)
                                true_count += 1
                    else:
                        # Formula-like sentence without = (description) — use as-is
                        q_true = {
                            'question_text': sent,
                            'correct_answer': 'True',
                            'question_type': 'true_false',
                            'difficulty_level': difficulty,
                            'bloom_level': bloom_level or 'remembering',
                            'topic': 'Mathematics',
                            'options': None,
                            'points': points,
                        }
                        if self._add_question_if_valid(q_true):
                            questions.append(q_true)
                            true_count += 1

                if len(questions) >= count:
                    break

                # FALSE: mutate and verify the mutation is actually false
                if false_count < false_budget:
                    mutated = self._math_mutate_for_false(sent)
                    if mutated and mutated != sent:
                        # SymPy gate: confirm mutation broke the equation
                        if verify_mutation_is_false(sent, mutated):
                            q_false = {
                                'question_text': mutated,
                                'correct_answer': 'False',
                                'question_type': 'true_false',
                                'difficulty_level': difficulty,
                                'bloom_level': bloom_level or 'remembering',
                                'topic': 'Mathematics',
                                'options': None,
                                'points': points,
                            }
                            if self._add_question_if_valid(q_false):
                                questions.append(q_false)
                                false_count += 1

            # Strategy B3: Conceptual T/F from definitions
            definitions = math_concepts.get('definitions', [])
            for i, defn in enumerate(definitions):
                if len(questions) >= count:
                    break
                term = defn.get('term', '').strip()
                definition = defn.get('definition', '').strip()
                if not term or not definition:
                    continue

                # TRUE form
                if true_count < true_budget:
                    stmt = f"{term} is defined as {definition}."
                    q_true = {
                        'question_text': stmt,
                        'correct_answer': 'True',
                        'question_type': 'true_false',
                        'difficulty_level': difficulty,
                        'bloom_level': bloom_level or 'understanding',
                        'topic': 'Mathematics',
                        'options': None,
                        'points': points,
                    }
                    if self._add_question_if_valid(q_true):
                        questions.append(q_true)
                        true_count += 1

                if len(questions) >= count:
                    break

                # FALSE form: swap with a different term
                if false_count < false_budget and len(definitions) > 1:
                    other = definitions[(i + 1) % len(definitions)]
                    wrong_term = other.get('term', '').strip()
                    if wrong_term and wrong_term != term:
                        stmt = f"{wrong_term} is defined as {definition}."
                        q_false = {
                            'question_text': stmt,
                            'correct_answer': 'False',
                            'question_type': 'true_false',
                            'difficulty_level': difficulty,
                            'bloom_level': bloom_level or 'understanding',
                            'topic': 'Mathematics',
                            'options': None,
                            'points': points,
                        }
                        if self._add_question_if_valid(q_false):
                            questions.append(q_false)
                            false_count += 1

            logger.info(f"        🔢 Math T/F: generated {len(questions)}/{count} (T:{true_count} F:{false_count})")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error in _math_generate_true_false: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return questions

    def _math_mutate_for_false(self, sentence):
        """Mutate a math sentence to make it false (swap operator, exponent, or coefficient)."""
        mutated = sentence
        # Try each mutation type in random order
        mutations = list(self._MATH_MUTATION_OPS.items())
        random.shuffle(mutations)
        for old, new in mutations:
            if old in mutated:
                # Only replace the first occurrence
                mutated = mutated.replace(old, new, 1)
                if mutated != sentence:
                    return mutated
        # Coefficient swap: find a number and change it
        numbers = re.findall(r'(?<![a-zA-Z])\d+(?:\.\d+)?(?![a-zA-Z])', sentence)
        for num in numbers:
            try:
                val = float(num)
                if val == 0:
                    continue
                new_val = val + random.choice([1, -1, 2])
                new_str = str(int(new_val)) if new_val == int(new_val) else f"{new_val:.2f}"
                if new_str != num:
                    return sentence.replace(num, new_str, 1)
            except ValueError:
                continue
        return None

    def _math_generate_fill_in_blank(self, text_content, difficulty, count, points,
                                      bloom_level='remembering', module_ids=None):
        """Generate fill-in-blank questions from math/equation content with SymPy verification."""
        from app.exam.math_solver import compute_missing_value

        questions = []
        try:
            # Phase A: DB-first (unchanged)
            if module_ids:
                db_qs = self._query_module_questions(
                    module_ids, None, difficulty, count * 4,
                    target_type='fill_in_blank', points=points
                )
                for q in db_qs:
                    if len(questions) >= count:
                        break
                    ans = (q.get('correct_answer') or '').strip()
                    if not ans or len(ans.split()) > 5:
                        continue
                    q_text = q.get('question_text', '')
                    if ans.lower() in q_text.lower():
                        blanked = re.sub(re.escape(ans), '_______', q_text, count=1, flags=re.IGNORECASE)
                        q['question_text'] = blanked
                    elif '_' * 3 not in q_text:
                        q['question_text'] = q_text + ': _______'
                    q['question_type'] = 'fill_in_blank'
                    q['bloom_level'] = bloom_level or 'remembering'
                    q['points'] = points
                    q['options'] = None
                    if self._add_question_if_valid(q):
                        questions.append(q)

            # Phase B: SymPy-verified formula-component blanking
            math_sents = getattr(self, '_math_sentences', [])
            blank_priority = {
                'easy': ['numbers', 'greek'],
                'medium': ['variables', 'numbers'],
                'hard': ['functions', 'operators', 'greek'],
            }
            priority = blank_priority.get(difficulty, ['numbers', 'variables'])

            _HINT_BY_DIFFICULTY = {
                'easy': ' (Substitute known values and simplify.)',
                'medium': ' (Rearrange the equation to isolate the unknown.)',
                'hard': ' (Apply algebraic manipulation — show each step.)',
            }

            for sent in math_sents:
                if len(questions) >= count:
                    break
                tokens = ExamGenerator._math_tokenize_equation(sent)

                target = None
                for category in priority:
                    candidates = tokens.get(category, [])
                    valid = [c for c in candidates if len(c) >= 1 and c not in ('=', '0', '1')]
                    if valid:
                        target = random.choice(valid)
                        break

                if not target:
                    continue

                blanked = sent.replace(target, '_______', 1)
                if blanked == sent:
                    continue

                # SymPy verification: solve for the blanked value
                verified_val = compute_missing_value(sent, target) if '=' in sent else None

                if verified_val is not None:
                    correct_str = str(round(verified_val, 4))
                    if '.' in correct_str:
                        correct_str = correct_str.rstrip('0').rstrip('.')
                    hint = _HINT_BY_DIFFICULTY.get(difficulty, '')
                    correct_answer = f"{correct_str}{hint}"
                else:
                    correct_answer = target

                stem = f"Complete the expression: {blanked}"
                q = {
                    'question_text': stem,
                    'correct_answer': correct_answer,
                    'question_type': 'fill_in_blank',
                    'difficulty_level': difficulty,
                    'bloom_level': bloom_level or 'remembering',
                    'topic': 'Mathematics',
                    'options': None,
                    'points': points,
                }
                if self._add_question_if_valid(q):
                    questions.append(q)

            logger.info(f"        🔢 Math FIB: generated {len(questions)}/{count}")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error in _math_generate_fill_in_blank: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return questions

    def _math_generate_identification(self, text_content, difficulty, count, points,
                                       bloom_level='remembering', module_ids=None):
        """Generate identification questions from math/equation content with semantic matching."""
        questions = []
        used_answers = set()
        try:
            # Phase A: DB-first (unchanged)
            if module_ids:
                db_qs = self._query_module_questions(
                    module_ids, None, difficulty, count * 4,
                    target_type='identification', points=points
                )
                for q in db_qs:
                    if len(questions) >= count:
                        break
                    ans = (q.get('correct_answer') or '').strip()
                    if not ans or len(ans.split()) > 15 or ans.lower() in used_answers:
                        continue
                    q['question_type'] = 'identification'
                    q['bloom_level'] = bloom_level or 'remembering'
                    q['points'] = points
                    q['options'] = None
                    if self._add_question_if_valid(q):
                        questions.append(q)
                        used_answers.add(ans.lower())

            math_concepts = getattr(self, '_math_concepts', {})
            math_sents = getattr(self, '_math_sentences', [])

            # Pre-encode math sentences for semantic matching (batch once)
            st = self._get_sentence_transformer()
            sent_embeddings = None
            sents_for_embed = math_sents[:50]
            if st and sents_for_embed:
                try:
                    sent_embeddings = st.encode(sents_for_embed, show_progress_bar=False)
                except Exception:
                    sent_embeddings = None

            # Phase B, Strategy 1: Variable identification (unchanged)
            for sent in math_sents:
                if len(questions) >= count:
                    break
                tokens = ExamGenerator._math_tokenize_equation(sent)
                for var in tokens['variables']:
                    if var.lower() in used_answers or len(var) < 1:
                        continue
                    desc_pat = re.compile(
                        r'\b' + re.escape(var) + r'\b\s*(?:is|represents?|denotes?|stands?\s+for|=)\s+'
                        r'([^.\n]{5,100})', re.IGNORECASE
                    )
                    desc_match = desc_pat.search(text_content)
                    if desc_match:
                        description = desc_match.group(1).strip()
                        stem = f"In the expression \"{sent}\", what does the variable '{var}' represent?"
                        q = {
                            'question_text': stem,
                            'correct_answer': description,
                            'question_type': 'identification',
                            'difficulty_level': difficulty,
                            'bloom_level': bloom_level or 'remembering',
                            'topic': 'Mathematics',
                            'options': None,
                            'points': points,
                        }
                        if self._add_question_if_valid(q):
                            questions.append(q)
                            used_answers.add(description.lower())
                            break

            # Phase B, Strategy 2: Formula/theorem recognition (semantic matching)
            theorems = math_concepts.get('theorems', [])
            for theorem in theorems:
                if len(questions) >= count:
                    break
                if theorem.lower() in used_answers:
                    continue

                related_eq = ''
                # Semantic matching via sentence-transformer
                if st and sent_embeddings is not None and len(sents_for_embed) > 0:
                    try:
                        theorem_emb = st.encode([theorem], show_progress_bar=False)[0]
                        t_norm = np.linalg.norm(theorem_emb)
                        if t_norm > 0:
                            best_sim, best_sent = 0.0, ''
                            for i, s_emb in enumerate(sent_embeddings):
                                s_norm = np.linalg.norm(s_emb)
                                if s_norm > 0:
                                    sim = float(np.dot(theorem_emb, s_emb) / (t_norm * s_norm))
                                    if sim > best_sim:
                                        best_sim = sim
                                        best_sent = sents_for_embed[i]
                            if best_sim >= 0.30 and best_sent:
                                related_eq = best_sent
                    except Exception:
                        pass

                # Fallback to word-overlap if semantic matching failed
                if not related_eq:
                    theorem_lower = theorem.lower()
                    for sent in math_sents:
                        if any(w in sent.lower() for w in theorem_lower.split() if len(w) > 2):
                            related_eq = sent
                            break

                if not related_eq:
                    continue

                stem = f"What formula or theorem is expressed as: {related_eq}?"
                q = {
                    'question_text': stem,
                    'correct_answer': theorem,
                    'question_type': 'identification',
                    'difficulty_level': difficulty,
                    'bloom_level': bloom_level or 'understanding',
                    'topic': 'Mathematics',
                    'options': None,
                    'points': points,
                }
                if self._add_question_if_valid(q):
                    questions.append(q)
                    used_answers.add(theorem.lower())

            # Phase B, Strategy 3: Definition-based identification (unchanged)
            for defn in math_concepts.get('definitions', []):
                if len(questions) >= count:
                    break
                term = defn.get('term', '').strip()
                definition = defn.get('definition', '').strip()
                if not term or not definition or term.lower() in used_answers:
                    continue
                stem = f"What term is defined as: {definition}?"
                q = {
                    'question_text': stem,
                    'correct_answer': term,
                    'question_type': 'identification',
                    'difficulty_level': difficulty,
                    'bloom_level': bloom_level or 'remembering',
                    'topic': 'Mathematics',
                    'options': None,
                    'points': points,
                }
                if self._add_question_if_valid(q):
                    questions.append(q)
                    used_answers.add(term.lower())

            # Phase B, Strategy 4: Formula-to-name (reverse direction)
            for theorem in theorems:
                if len(questions) >= count:
                    break
                if theorem.lower() in used_answers:
                    continue
                # Find associated formula
                assoc_formula = None
                for sent in math_sents:
                    if any(w.lower() in sent.lower() for w in theorem.split() if len(w) > 3):
                        assoc_formula = sent
                        break
                if not assoc_formula:
                    continue
                stem = f"State the formula or expression associated with {theorem}."
                q = {
                    'question_text': stem,
                    'correct_answer': assoc_formula,
                    'question_type': 'identification',
                    'difficulty_level': difficulty,
                    'bloom_level': bloom_level or 'remembering',
                    'topic': 'Mathematics',
                    'options': None,
                    'points': points,
                }
                if self._add_question_if_valid(q):
                    questions.append(q)
                    used_answers.add(theorem.lower())

            logger.info(f"        🔢 Math Identification: generated {len(questions)}/{count}")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error in _math_generate_identification: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return questions

    def _math_find_relevant_context(self, concept, text_content, math_sents,
                                      n=3, precomputed_sents=None, precomputed_embs=None):
        """
        Find the n most semantically relevant sentences for *concept* using
        sentence-transformer.  Falls back to word-overlap when the transformer
        is unavailable.  Returns a joined string of the best matches.
        """
        # Build candidate pool
        if precomputed_sents is not None:
            combined = precomputed_sents
        else:
            all_sents = [s for s in self._sent_tokenize(text_content)
                         if len(s) >= 20][:200]
            combined = list(dict.fromkeys(math_sents[:50] + all_sents[:150]))

        if not combined:
            return f"Analysis based on the mathematical properties of {concept}."

        st = self._get_sentence_transformer()

        if st:
            try:
                query_emb = st.encode([concept], show_progress_bar=False)[0]
                q_norm = np.linalg.norm(query_emb)
                if q_norm > 0:
                    if precomputed_embs is not None:
                        sent_embs = precomputed_embs
                    else:
                        sent_embs = st.encode(combined, show_progress_bar=False)

                    sims = []
                    for i, emb in enumerate(sent_embs):
                        s_norm = np.linalg.norm(emb)
                        if s_norm > 0:
                            sim = float(np.dot(query_emb, emb) / (q_norm * s_norm))
                            sims.append((sim, combined[i]))
                    sims.sort(key=lambda x: -x[0])
                    top = [s for sc, s in sims[:n] if sc >= 0.25]
                    if top:
                        return ' '.join(top)
            except Exception:
                pass

        # Word-overlap fallback
        concept_words = set(w.lower() for w in concept.split() if len(w) > 2)
        scored = []
        for s in combined:
            s_words = set(w.lower() for w in s.split())
            overlap = len(concept_words & s_words)
            if overlap > 0:
                scored.append((overlap, s))
        scored.sort(key=lambda x: -x[0])
        top = [s for _, s in scored[:n]]
        if top:
            return ' '.join(top)
        return f"Analysis based on the mathematical properties of {concept}."

    def _math_generate_analysis(self, text_content, difficulty, count, points,
                                 bloom_level='analyzing', module_ids=None):
        """Generate analysis questions from math/equation content with context-derived answers."""
        questions = []
        try:
            # Phase A: DB-first (unchanged)
            if module_ids:
                db_qs = self._query_module_questions(
                    module_ids, 'analysis', difficulty, count * 4,
                    target_type='analysis', points=points
                )
                for q in db_qs:
                    if len(questions) >= count:
                        break
                    q['question_type'] = 'analysis'
                    q['bloom_level'] = bloom_level or 'analyzing'
                    q['points'] = points
                    q['options'] = None
                    if self._add_question_if_valid(q):
                        questions.append(q)

            # Phase B: Template-based math analysis with semantic answers
            math_concepts = getattr(self, '_math_concepts', {})
            math_sents = getattr(self, '_math_sentences', [])
            templates = self._MATH_ANALYSIS_TEMPLATES[:]
            random.shuffle(templates)

            # Build concept pool
            concept_pool = []
            for t in math_concepts.get('theorems', []):
                concept_pool.append(t)
            for d in math_concepts.get('definitions', []):
                concept_pool.append(d.get('term', ''))
            concept_pool = [c for c in dict.fromkeys(concept_pool) if c]

            equation_pool = math_concepts.get('equations', [])

            # Pre-compute sentence embeddings once for context retrieval
            all_sents = [s for s in self._sent_tokenize(text_content)
                         if len(s) >= 20][:200]
            context_sents = list(dict.fromkeys(math_sents[:50] + all_sents[:150]))
            context_embs = None
            st = self._get_sentence_transformer()
            if st and context_sents:
                try:
                    context_embs = st.encode(context_sents, show_progress_bar=False)
                except Exception:
                    context_embs = None

            template_idx = 0
            for concept in concept_pool:
                if len(questions) >= count:
                    break
                tmpl = templates[template_idx % len(templates)]
                template_idx += 1

                # Find a related equation
                eq = ''
                for s in math_sents:
                    if any(w.lower() in s.lower() for w in concept.split() if len(w) > 2):
                        eq = s
                        break
                if not eq and equation_pool:
                    eq = random.choice(equation_pool)

                # Find a variable from the equation
                var = 'x'
                if eq:
                    t = ExamGenerator._math_tokenize_equation(eq)
                    if t['variables']:
                        var = random.choice(t['variables'])

                q_text = tmpl.format(
                    concept=concept,
                    equation=eq or concept,
                    variable=var,
                )

                # Semantic context retrieval for the answer
                answer = self._math_find_relevant_context(
                    concept, text_content, math_sents, n=3,
                    precomputed_sents=context_sents,
                    precomputed_embs=context_embs,
                )

                q = {
                    'question_text': q_text,
                    'correct_answer': answer,
                    'question_type': 'analysis',
                    'difficulty_level': difficulty,
                    'bloom_level': bloom_level or 'analyzing',
                    'topic': concept[:100],
                    'options': None,
                    'points': points,
                }
                if self._add_question_if_valid(q):
                    questions.append(q)

            # If concept pool is exhausted, generate from equations directly
            for eq in equation_pool:
                if len(questions) >= count:
                    break
                tokens = ExamGenerator._math_tokenize_equation(eq)
                var = tokens['variables'][0] if tokens['variables'] else 'x'
                q_text = f"Analyze the relationship between the variables in: {eq}. How does changing {var} affect the result?"

                # Context-derived answer instead of generic placeholder
                answer = self._math_find_relevant_context(
                    eq, text_content, math_sents, n=2,
                    precomputed_sents=context_sents,
                    precomputed_embs=context_embs,
                )

                q = {
                    'question_text': q_text,
                    'correct_answer': answer,
                    'question_type': 'analysis',
                    'difficulty_level': difficulty,
                    'bloom_level': bloom_level or 'analyzing',
                    'topic': 'Mathematics',
                    'options': None,
                    'points': points,
                }
                if self._add_question_if_valid(q):
                    questions.append(q)

            logger.info(f"        🔢 Math Analysis: generated {len(questions)}/{count}")
            return questions

        except Exception as e:
            logger.error(f"        ❌ Error in _math_generate_analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return questions

    # ======================================================================
    # END MATH MODE GENERATORS
    # ======================================================================

    def _extract_context_for_keyword(self, text, keyword, window=2):
        """Extract context sentences around keyword (for MCQ)"""
        sentences = text.split(".")
        
        for i, sentence in enumerate(sentences):
            if keyword.lower() in sentence.lower():
                start = max(0, i - window)
                end = min(len(sentences), i + window + 1)
                context = ". ".join(sentences[start:end]).strip()
                return context
        
        return None
    
    def _phase3_question_generation_strategy(self, text_content, exam_config):
        """
        PHASE 3: Question Generation Strategy
        Analyzes content and creates comprehensive question distribution strategy
        """
        logger.info("=" * 80)
        logger.info("📋 PHASE 3: QUESTION GENERATION STRATEGY")
        logger.info("=" * 80)

        try:
            # Analyze content characteristics
            text_length = len(text_content)
            word_count = len(text_content.split())
            sentences = self._sent_tokenize(text_content)
            sentence_count = len([s for s in sentences if len(s) > 10])

            logger.info(f"Content Analysis:")
            logger.info(f"  - Text length: {text_length:,} characters")
            logger.info(f"  - Word count: {word_count:,} words")
            logger.info(f"  - Sentences: {sentence_count}")

            # Extract and analyze keywords for coverage
            self.tfidf_engine.add_document(text_content)
            keywords = self.tfidf_engine.extract_keywords(text_content, top_n=100)

            # AI ENHANCEMENT: Enhance keywords with NLP
            enhanced_keywords = self._enhance_keyword_selection_with_nlp(text_content, keywords)

            logger.info(f"  - Keywords identified: {len(enhanced_keywords)} (AI-enhanced)")

            # Analyze linguistic features for question potential
            linguistic_features = self._extract_linguistic_features(text_content)
            if linguistic_features:
                logger.info(f"  - Noun phrases: {len(linguistic_features.get('noun_phrases', []))}")
                logger.info(f"  - Named entities: {len(linguistic_features.get('named_entities', []))}")
                logger.info(f"  - Important nouns: {len(linguistic_features.get('important_nouns', []))}")

            # Analyze question type distribution from config
            question_types_details = exam_config.get('question_types_details', [])
            total_questions = exam_config.get('num_questions', 0)

            logger.info(f"\nQuestion Distribution Strategy:")
            logger.info(f"  - Total questions needed: {total_questions}")

            coverage_strategy = {
                'total_questions': total_questions,
                'content_density': word_count / max(total_questions, 1),
                'keywords': enhanced_keywords[:50],
                'linguistic_features': linguistic_features,
                'type_distribution': {}
            }

            for qt_config in question_types_details:
                q_type = qt_config['type']
                q_count = qt_config['count']
                q_points = qt_config['points']
                difficulty_dist = qt_config['difficulty_distribution']

                logger.info(f"  - {q_type}: {q_count} questions ({q_points} pts each)")
                for diff, count in difficulty_dist.items():
                    if count > 0:
                        logger.info(f"    • {diff}: {count}")

                coverage_strategy['type_distribution'][q_type] = {
                    'count': q_count,
                    'points': q_points,
                    'difficulty': difficulty_dist,
                    'coverage_per_question': word_count / max(q_count, 1)
                }

            # Calculate coverage metrics
            logger.info(f"\nCoverage Metrics:")
            logger.info(f"  - Words per question: {coverage_strategy['content_density']:.1f}")
            logger.info(f"  - Keywords available per question: {len(enhanced_keywords) / max(total_questions, 1):.1f}")

            logger.info("✅ PHASE 3 COMPLETE: Strategy defined")
            logger.info("=" * 80)

            return coverage_strategy

        except Exception as e:
            logger.error(f"❌ Error in Phase 3: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _phase5_answer_verification(self, questions, text_content):
        """
        PHASE 5: Answer Verification
        Cross-references answers with source content and performs quality assurance
        """
        logger.info("=" * 80)
        logger.info("🔍 PHASE 5: ANSWER VERIFICATION & QUALITY ASSURANCE")
        logger.info("=" * 80)

        verified_questions = []
        verification_stats = {
            'total': len(questions),
            'verified': 0,
            'rejected': 0,
            'warnings': 0
        }

        try:
            for idx, question in enumerate(questions):
                verification_passed = True
                warnings = []

                q_text = self._sanitize_generated_text(question.get('question_text', ''))
                q_type = question.get('question_type', '')
                correct_answer = question.get('correct_answer', '')
                if isinstance(correct_answer, str):
                    correct_answer = self._sanitize_generated_text(correct_answer)
                    question['correct_answer'] = correct_answer

                options = question.get('options', [])
                if isinstance(options, list):
                    options = [
                        self._sanitize_generated_text(option) if isinstance(option, str) else option
                        for option in options
                    ]
                    question['options'] = options

                question['question_text'] = q_text

                # Verification Check 1: Answer exists in source content
                # problem_solving answers are full step-by-step solutions — skip
                # content-match for them and just confirm the answer is non-empty.
                if q_type == 'problem_solving':
                    if not correct_answer or len(correct_answer.strip()) < 20:
                        verification_passed = False
                        logger.warning(f"  ❌ Q{idx+1}: Problem-solving answer is empty or too short")
                elif correct_answer and isinstance(correct_answer, str):
                    answer_lower = correct_answer.lower()

                    # Check if answer appears in content
                    if answer_lower not in text_content.lower():
                        # For short answers, this might be expected (e.g., "True", "False")
                        if q_type not in ['true_false'] and len(answer_lower) > 4:
                            warnings.append(f"Answer '{correct_answer}' not found in source content")
                            verification_stats['warnings'] += 1

                # Verification Check 2: Question quality checks
                if len(q_text.strip()) < 10:
                    verification_passed = False
                    logger.warning(f"  WARN Q{idx+1}: Too short - '{q_text[:50]}...'")

                if self._has_text_artifact(q_text):
                    verification_passed = False
                    logger.warning(f"  REJECT Q{idx+1}: Text artifact detected after sanitization")

                # Reject spaced-letter artifacts and template-like stems
                if re.search(r'(?:[A-Za-z]\\s){6,}', q_text):
                    verification_passed = False
                    logger.warning(f"  REJECT Q{idx+1}: Spaced-letter artifact detected")

                if q_type in ['multiple_choice', 'true_false', 'fill_in_blank', 'identification']:
                    if self._question_looks_copied_from_source(q_text, text_content):
                        rewritten_stem = self._rewrite_copied_objective_stem(question, text_content)
                        if rewritten_stem:
                            q_text = rewritten_stem
                            question['question_text'] = rewritten_stem
                            warnings.append("Stem rewritten during verification to reduce source copying")
                            verification_stats['warnings'] += 1
                            logger.info(f"  🔄 Q{idx+1}: Rewrote copied stem during verification")
                        else:
                            verification_passed = False
                            logger.warning(f"  REJECT Q{idx+1}: Question text copies the source too closely")

                # Avoid generic template stems that produced poor questions.
                # Keep as warning-only in balanced mode to reduce over-rejection.
                if "complete the sentence" in q_text.lower() or "what term completes" in q_text.lower():
                    warnings.append("Generic template stem detected")
                    verification_stats['warnings'] += 1
                    logger.warning(f"  WARN Q{idx+1}: Generic template stem detected")

                # Answer leakage: if the answer string is already in the stem, reject for objective types
                if correct_answer and isinstance(correct_answer, str):
                    answer_for_leak = correct_answer.strip()
                    if len(answer_for_leak) >= 4 and re.search(re.escape(answer_for_leak), q_text, flags=re.IGNORECASE):
                        if q_type in ['multiple_choice', 'fill_in_blank', 'identification']:
                            verification_passed = False
                            logger.warning(f"  REJECT Q{idx+1}: Answer appears in question text")
                        else:
                            warnings.append("Answer appears in question text")
                            verification_stats['warnings'] += 1

                # Verification Check 3: MCQ specific checks
                if q_type == 'multiple_choice':
                    # Must have exactly 4 options: 1 correct answer + 3 distractors
                    if len(options) != 4:
                        verification_passed = False
                        logger.warning(f"  ❌ Q{idx+1}: MCQ must have exactly 4 options")

                    # Correct answer must be in options
                    elif correct_answer not in options:
                        verification_passed = False
                        logger.warning(f"  ❌ Q{idx+1}: Correct answer not in options")

                    # Check for duplicate options
                    elif len(options) != len(set(options)):
                        verification_passed = False
                        logger.warning(f"  ❌ Q{idx+1}: Duplicate options detected")

                    # AI ENHANCEMENT: Semantic validation
                    else:
                        semantic_valid = self._validate_mcq_options_semantic(question)
                        if not semantic_valid:
                            warnings.append("Semantic similarity concerns detected")
                            verification_stats['warnings'] += 1

                # Verification Check 4: Fill-in-blank checks
                if q_type == 'fill_in_blank':
                    if '______' not in q_text and '_____' not in q_text:
                        verification_passed = False
                        logger.warning(f"  ❌ Q{idx+1}: Fill-in-blank missing blank marker")

                # Verification Check 4b: Problem-solving must NOT have blanks
                if q_type == 'problem_solving':
                    if '______' in q_text or '_____' in q_text:
                        verification_passed = False
                        logger.warning(f"  ❌ Q{idx+1}: Problem-solving question must not contain blanks")

                # Verification Check 5: True/False checks
                if q_type == 'true_false':
                    if correct_answer not in ['True', 'False']:
                        verification_passed = False
                        logger.warning(f"  ❌ Q{idx+1}: T/F answer must be 'True' or 'False'")

                # Add verification metadata
                if verification_passed:
                    question['verified'] = True
                    question['verification_warnings'] = warnings if warnings else None
                    verified_questions.append(question)
                    verification_stats['verified'] += 1

                    if warnings:
                        logger.info(f"  ✅ Q{idx+1}: Verified with {len(warnings)} warning(s)")
                else:
                    verification_stats['rejected'] += 1
                    logger.warning(f"  ❌ Q{idx+1}: Rejected - failed verification")

            # Log verification summary
            logger.info(f"\nVerification Summary:")
            logger.info(f"  - Total questions: {verification_stats['total']}")
            logger.info(f"  - Verified: {verification_stats['verified']}")
            logger.info(f"  - Rejected: {verification_stats['rejected']}")
            logger.info(f"  - Warnings: {verification_stats['warnings']}")
            logger.info(f"  - Pass rate: {(verification_stats['verified']/max(verification_stats['total'],1)*100):.1f}%")

            logger.info("✅ PHASE 5 COMPLETE: Verification done")
            logger.info("=" * 80)

            return verified_questions, verification_stats

        except Exception as e:
            logger.error(f"❌ Error in Phase 5: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return questions, verification_stats

    @staticmethod
    def _merge_verification_stats(base_stats, new_stats):
        """Merge verification stats across multiple verification passes."""
        merged = dict(base_stats or {})
        for key in ('total', 'verified', 'rejected', 'warnings'):
            merged[key] = int(merged.get(key, 0)) + int((new_stats or {}).get(key, 0))
        return merged

    def _refill_verified_question_shortfalls(self, text_content, exam_config, verified_questions, verification_stats):
        """
        Refill missing per-type/per-difficulty slots after verification rejects items.

        This keeps the teacher's configured layout intact without using cross-type substitution.
        """
        target_configs = exam_config.get('question_types_details', []) or []
        if not target_configs:
            return verified_questions, verification_stats

        max_passes = 10  # Increased from 5 to handle higher rejection rates
        for attempt in range(max_passes):
            deficits = []
            for qt_config in target_configs:
                qt_type = qt_config['type']
                for difficulty, target_count in (qt_config.get('difficulty_distribution') or {}).items():
                    if target_count <= 0:
                        continue
                    current_count = sum(
                        1 for q in verified_questions
                        if q.get('question_type') == qt_type and q.get('difficulty_level') == difficulty
                    )
                    missing = target_count - current_count
                    if missing > 0:
                        deficits.append((qt_config, difficulty, missing))

            if not deficits:
                logger.info("✅ Post-verification refill not needed — all configured slots are filled.")
                break

            logger.warning(
                f"⚠️  Post-verification refill pass {attempt + 1}/{max_passes} "
                f"starting with {sum(missing for _, _, missing in deficits)} missing slots."
            )

            gained_this_pass = 0
            for qt_config, difficulty, missing in deficits:
                question_type = qt_config['type']
                points = qt_config['points']
                bloom_level = qt_config.get('bloom_level', None)
                request_count = missing + min(max(missing, 1), 4)

                extra_questions = self._generate_questions_by_type(
                    text_content=text_content,
                    question_type=question_type,
                    difficulty=difficulty,
                    count=request_count,
                    points=points,
                    bloom_level=bloom_level,
                    module_ids=exam_config.get('module_ids', []),
                )
                if not extra_questions:
                    continue

                verified_extra, extra_stats = self._phase5_answer_verification(extra_questions, text_content)
                verification_stats = self._merge_verification_stats(verification_stats, extra_stats)
                if not verified_extra:
                    continue

                accepted_extra = verified_extra[:missing]
                if not accepted_extra:
                    continue

                verified_questions.extend(accepted_extra)
                gained_this_pass += len(accepted_extra)
                logger.info(
                    f"  🔄 Refill accepted +{len(accepted_extra)} {question_type} "
                    f"({difficulty}) after verification from {len(extra_questions)} candidates."
                )

            if gained_this_pass <= 0:
                logger.warning("⚠️  Post-verification refill could not recover any additional valid questions.")
                break

        return verified_questions, verification_stats

    def generate_exam(self, module_content, exam_config):
        """
        COMPREHENSIVE 7-PHASE EXAM GENERATION WORKFLOW

        Phase 1: Module Extraction (handled externally in saved_module.py)
        Phase 2: Content Analysis (performed at exam generation start)
        Phase 3: Question Generation Strategy
        Phase 4: Question Writing
        Phase 5: Answer Verification
        Phase 6: Formatting and Organization
        Phase 7: Output and Delivery
        """
        try:
            self.reset_question_tracking()

            logger.info("=" * 100)
            logger.info("🚀 7-PHASE EXAM GENERATION WORKFLOW - AI-ENHANCED v3.0")
            logger.info("=" * 100)
            logger.info(f"Title: {exam_config.get('title')}")
            logger.info(f"Target: {exam_config.get('num_questions')} questions")
            logger.info("=" * 100)

            raw_targets = exam_config.get('module_question_targets') or {}
            parsed_targets = {}
            if isinstance(raw_targets, list):
                for item in raw_targets:
                    try:
                        module_id = int(item.get('module_id'))
                        count = int(item.get('count', 0))
                        if count > 0:
                            parsed_targets[module_id] = count
                    except Exception:
                        continue
            elif isinstance(raw_targets, dict):
                for module_id, count in raw_targets.items():
                    try:
                        count_int = int(count)
                        module_id_int = int(module_id)
                        if count_int > 0:
                            parsed_targets[module_id_int] = count_int
                    except Exception:
                        continue

            self._module_question_targets = parsed_targets
            self._module_question_usage = {module_id: 0 for module_id in parsed_targets}
            if self._module_question_targets:
                logger.info(f"Module target distribution: {self._module_question_targets}")

            # ===== PHASE 2: CONTENT ANALYSIS =====
            logger.info("📊 PHASE 2: CONTENT ANALYSIS")
            logger.info("=" * 80)

            text_content = self._extract_text_content(module_content)
            logger.info(f"Extracted content: {len(text_content):,} characters")

            # ── Math mode detection (runs on raw text BEFORE cleaning) ──
            self._math_mode = ExamGenerator._detect_math_mode(text_content)
            if self._math_mode:
                self._math_sentences = self._extract_math_sentences(text_content)
                self._math_concepts  = self._extract_math_concepts(text_content)
                logger.info(
                    f"🔢 Math mode ACTIVE — {len(self._math_sentences)} math sentences, "
                    f"{len(self._math_concepts.get('equations', []))} equations, "
                    f"{len(self._math_concepts.get('theorems', []))} theorems detected"
                )

            # Clean text for processing
            clean_text = self._clean_text_for_questions(text_content)
            logger.info(f"Cleaned content: {len(clean_text):,} characters")

            # Reset NLP engine
            if hasattr(self.nlp_engine, 'reset_generated_questions'):
                self.nlp_engine.reset_generated_questions()

            logger.info("✅ PHASE 2 COMPLETE: Content analyzed")
            logger.info("=" * 80)

            # ===== PHASE 3: QUESTION GENERATION STRATEGY =====
            strategy = self._phase3_question_generation_strategy(clean_text, exam_config)
            if not strategy:
                return {
                    'success': False,
                    'message': 'Failed to create question generation strategy'
                }

            # ===== PHASE 4: QUESTION WRITING =====
            logger.info("=" * 80)
            logger.info("✍️ PHASE 4: QUESTION WRITING")
            logger.info("=" * 80)

            questions = self._distribute_questions_by_type_and_difficulty(module_content, exam_config)

            if questions is None or len(questions) == 0:
                return {
                    'success': False,
                    'message': 'Failed to generate questions'
                }

            # No cross-type top-up here.
            # Type-locked top-up is handled inside _distribute_questions_by_type_and_difficulty.
            target_total = exam_config.get('num_questions', len(questions))
            if len(questions) < target_total:
                missing = target_total - len(questions)
                logger.warning(
                    f"⚠️  Generated {len(questions)}/{target_total}; "
                    f"skipping cross-type fallback (same-type lock enabled), short by {missing}"
                )

            logger.info(f"Generated {len(questions)} questions")
            logger.info("✅ PHASE 4 COMPLETE: Questions written")
            logger.info("=" * 80)

            # ===== PHASE 5: ANSWER VERIFICATION =====
            verified_questions, verification_stats = self._phase5_answer_verification(questions, text_content)

            verified_questions, verification_stats = self._refill_verified_question_shortfalls(
                text_content=text_content,
                exam_config=exam_config,
                verified_questions=verified_questions,
                verification_stats=verification_stats,
            )

            if len(verified_questions) == 0:
                return {
                    'success': False,
                    'message': 'No questions passed verification'
                }

            target_total = exam_config.get('num_questions', len(verified_questions))
            if len(verified_questions) < target_total:
                logger.warning(
                    f"⚠️  Verified output remains short after refill: "
                    f"{len(verified_questions)}/{target_total}"
                )

            # Enforce requested Bloom distribution for TOS/reporting.
            verified_questions = self._apply_target_bloom_distribution(
                verified_questions,
                exam_config.get('cognitive_distribution')
            )

            # ===== PHASE 6: FORMATTING AND ORGANIZATION =====
            logger.info("=" * 80)
            logger.info("📝 PHASE 6: FORMATTING & ORGANIZATION")
            logger.info("=" * 80)

            # Extract topics for TOS
            topics = self._extract_topics(module_content)
            logger.info(f"Identified {len(topics)} topics")

            # Generate Table of Specifications
            tos = self.tos_generator.generate_tos(verified_questions, topics, exam_config)
            logger.info("Generated Table of Specifications")

            # Group questions by type
            grouped_questions = self.randomizer.group_by_question_type(verified_questions)
            logger.info(f"Grouped into question types: {len(set(q['question_type'] for q in grouped_questions))}")

            # Randomize options for MCQ
            grouped_questions = self.randomizer.randomize_options(grouped_questions)
            logger.info("Randomized MCQ options")

            # Apply per-question-type instructions from configuration.
            # Behavior: first question of each type gets the instruction prepended.
            default_section_instruction_map = {
                'multiple_choice': 'Choose the best answer for each question.',
                'true_false': 'Write TRUE if the statement is correct; otherwise write FALSE.',
                'fill_in_blank': 'Fill in each blank with the correct answer.',
                'identification': 'Identify the correct term or concept for each item.',
            }
            section_instruction_map = {}
            for qt in exam_config.get('question_types_details', []) or []:
                qt_type = str(qt.get('type') or '').strip()
                custom_instruction = str(qt.get('description') or '').strip()
                instruction_text = custom_instruction or default_section_instruction_map.get(qt_type, '')
                if qt_type and instruction_text and qt_type not in section_instruction_map:
                    section_instruction_map[qt_type] = instruction_text

            if section_instruction_map:
                seen_instruction_types = set()
                for question in grouped_questions:
                    q_type = str(question.get('question_type') or '').strip()
                    if not q_type or q_type in seen_instruction_types:
                        continue

                    instruction_text = section_instruction_map.get(q_type)
                    if not instruction_text:
                        continue

                    question['section_instruction'] = instruction_text
                    seen_instruction_types.add(q_type)

                        # Auto image attachment removed to avoid mismatched visuals
# Add metadata to questions
            for idx, question in enumerate(grouped_questions):
                question['question_number'] = idx + 1
                question['exam_title'] = exam_config.get('title', 'Untitled Exam')

            total_points = sum(q.get('points', 0) for q in grouped_questions)

            logger.info(f"Total points: {total_points}")

            # Score-target guard.
            # Balanced default: continue generation even when score is off.
            # Set exam_config.strict_score_match=true to keep fail-fast behavior.
            strict_score_match = bool(exam_config.get('strict_score_match', False))
            _target_total = sum(
                qt.get('count', 0) * qt.get('points', 0)
                for qt in exam_config.get('question_types_details', [])
            )
            if _target_total <= 0:
                return {
                    'success': False,
                    'message': (
                        'Cannot generate exam: invalid total score target from '
                        'question type settings. Please set valid points/count '
                        'values and try again.'
                    )
                }
            score_mismatch = None
            if total_points != _target_total:
                delta = total_points - _target_total
                mismatch = (
                    f"short by {abs(delta)} pts"
                    if delta < 0 else
                    f"exceeds by {delta} pts"
                )
                score_mismatch = {
                    'generated_points': total_points,
                    'target_points': _target_total,
                    'delta': delta,
                    'message': mismatch,
                }
                if strict_score_match:
                    logger.error(
                        f"❌ Score target mismatch: generated {total_points} pts, "
                        f"target {_target_total} pts ({mismatch}). Aborting exam generation."
                    )
                    return {
                        'success': False,
                        'message': (
                            f"Cannot generate exam: total score mismatch "
                            f"(generated {total_points} pts, target {_target_total} pts, {mismatch}). "
                            f"Please adjust module coverage, question settings, or uploaded content."
                        ),
                        'generated_points': total_points,
                        'target_points': _target_total,
                        'error_code': 'SCORE_TARGET_MISMATCH',
                    }
                logger.warning(
                    f"⚠️ Score target mismatch: generated {total_points} pts, "
                    f"target {_target_total} pts ({mismatch}). Continuing in balanced mode."
                )

            logger.info("✅ PHASE 6 COMPLETE: Formatted and organized")
            logger.info("=" * 80)

            # ===== PHASE 7: OUTPUT AND DELIVERY =====
            logger.info("=" * 80)
            logger.info("📤 PHASE 7: OUTPUT & DELIVERY")
            logger.info("=" * 80)

            # Prepare comprehensive output
            output = {
                'success': True,
                'exam_metadata': {
                    'title': exam_config.get('title', 'Untitled Exam'),
                    'total_questions': len(grouped_questions),
                    'total_points': total_points,
                    'target_points': _target_total,
                    'score_target_match': total_points == _target_total,
                    'score_mismatch': score_mismatch,
                    'question_types': list(set(q['question_type'] for q in grouped_questions)),
                    'difficulty_distribution': {
                        'easy': sum(1 for q in grouped_questions if q.get('difficulty_level') == 'easy'),
                        'medium': sum(1 for q in grouped_questions if q.get('difficulty_level') == 'medium'),
                        'hard': sum(1 for q in grouped_questions if q.get('difficulty_level') == 'hard')
                    },
                    'generation_timestamp': datetime.now().isoformat(),
                    'ai_enhanced': True,
                    'verification_stats': verification_stats
                },
                'questions': grouped_questions,
                'tos': tos,
                'topics': topics,
                'section_instructions': section_instruction_map,
                'total_questions': len(grouped_questions)
            }

            logger.info("Prepared output with metadata")
            logger.info("✅ PHASE 7 COMPLETE: Ready for delivery")

            logger.info("=" * 100)
            logger.info("✅ 7-PHASE WORKFLOW COMPLETE")
            logger.info(f"   Generated: {len(grouped_questions)} questions")
            logger.info(f"   Verified: {verification_stats['verified']}/{verification_stats['total']}")
            logger.info(f"   Total Points: {total_points}")
            logger.info(f"   Target Match: {'✅' if len(grouped_questions) >= exam_config.get('num_questions') * 0.9 else '⚠️'}")
            logger.info("=" * 100)

            return output

        except Exception as e:
            logger.error(f"❌ Error in exam generation: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': str(e)
            }
