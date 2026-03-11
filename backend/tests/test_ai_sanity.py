"""
tests/test_ai_sanity.py

AI sanity suite — four categories of assertions:

  Test                         Mark           Requires model?
  ──────────────────────────── ───────────── ─────────────────
  test_keyword_count           fast           No (pure Python)
  test_entity_count            requires_model spaCy en_core_web_sm
  test_dedup_delta             requires_model sentence-transformers
  test_T5_on_off_delta_mocked  fast           No (mocked)
  test_T5_on_off_delta_real    requires_model T5 t5-small

Run fast tests only:
    pytest -m fast -v

Run everything (needs models cached):
    pytest -v
"""
import sys
import os
import re
import pytest
from unittest.mock import MagicMock, patch

# Make `app` importable without a running Flask server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ===========================================================================
# Test 1 — keyword_count
# Pure TFIDFEngine test: no model download, no Flask app context.
# ===========================================================================
@pytest.mark.fast
def test_keyword_count(sample_text):
    """
    TFIDFEngine on a 250-word ML text must extract >= 5 keywords.
    """
    with patch("app.exam.tfidf_engine.logger"):
        from app.exam.tfidf_engine import TFIDFEngine

    engine = TFIDFEngine(min_word_length=3, max_word_length=50)

    # Split sample text into sentences and add each as a document
    sentences = [s.strip() for s in re.split(r"[.!?]+", sample_text) if s.strip()]
    for sent in sentences:
        engine.add_document(sent)
    engine.compute_idf()

    combined = " ".join(sentences)
    keywords = engine.extract_keywords(combined, top_n=30)

    assert len(keywords) >= 5, (
        f"Expected >= 5 keywords from ML text, got {len(keywords)}: {keywords}"
    )
    # All returned items must be (word, score) tuples
    for kw, score in keywords:
        assert isinstance(kw, str) and len(kw) >= 2, f"Bad keyword: {kw!r}"
        assert isinstance(score, float) and score >= 0, f"Bad score: {score}"


# ===========================================================================
# Test 2 — entity_count
# Requires spaCy en_core_web_sm to be installed.
# ===========================================================================
@pytest.mark.requires_model
def test_entity_count(sample_entity_text):
    """
    spaCy NER on a text with 4 known named entities must return >= 3.
    """
    spacy = pytest.importorskip("spacy", reason="spaCy not installed")
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("en_core_web_sm model not available in this environment")

    doc = nlp(sample_entity_text)
    entities = [
        ent.text for ent in doc.ents
        if ent.label_ in {"PERSON", "ORG", "GPE", "DATE", "LOC", "NORP", "FAC"}
    ]

    assert len(entities) >= 3, (
        f"Expected >= 3 named entities in text, found {len(entities)}: {entities}"
    )


# ===========================================================================
# Test 3 — dedup_delta
# Requires sentence-transformers (all-MiniLM-L6-v2).
# Validates the Feature 4 streaming algorithm directly.
# ===========================================================================
@pytest.mark.requires_model
def test_dedup_delta(sample_sentences_with_dupes):
    """
    Streaming dedup of 10 sentences (3 near-duplicates) must yield 5 ≤ N ≤ 8.
    """
    import numpy as np

    try:
        from sentence_transformers import SentenceTransformer
        transformer = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as exc:
        pytest.skip(f"sentence-transformers or model unavailable: {exc}")

    sentences    = sample_sentences_with_dupes
    THRESHOLD    = 0.85

    embeddings = transformer.encode(sentences)
    emb_arr    = np.array(embeddings, dtype=np.float32)
    norms      = np.linalg.norm(emb_arr, axis=1, keepdims=True)
    norms      = np.where(norms == 0, 1.0, norms)
    emb_norm   = emb_arr / norms

    keep_indices = []
    keep_matrix  = None
    removed      = 0

    for i in range(len(sentences)):
        if keep_matrix is not None:
            sims = keep_matrix @ emb_norm[i]
            if float(sims.max()) > THRESHOLD:
                removed += 1
                continue
        keep_indices.append(i)
        row = emb_norm[i:i+1]
        keep_matrix = row if keep_matrix is None else np.vstack([keep_matrix, row])

    deduped = [sentences[idx] for idx in keep_indices]

    assert len(deduped) <= 8, (
        f"Expected <= 8 after dedup (3 near-dupes in 10), got {len(deduped)}: {deduped}"
    )
    assert len(deduped) >= 5, (
        f"Dedup too aggressive — only {len(deduped)} sentences remain"
    )
    assert removed >= 2, (
        f"Expected >= 2 sentences removed as near-duplicates, removed only {removed}"
    )


# ===========================================================================
# Test 4a — T5_on_off_delta (mocked — fast, no model download)
# ===========================================================================
@pytest.mark.fast
def test_T5_on_off_delta_mocked():
    """
    When _generate_with_t5 returns realistic output → generate_question returns a dict.
    When _generate_with_t5 returns None → generate_question returns None.
    No T5 model is loaded; everything is mocked.
    """
    with patch("app.exam.t5_generator.logger"):
        from app.exam.t5_generator import T5QuestionGenerator

    # Skip model __init__ entirely
    with patch.object(T5QuestionGenerator, "__init__", lambda self, model_name=None: None):
        gen = object.__new__(T5QuestionGenerator)
        # Set the minimum attributes that generate_question relies on
        gen.model_name = "t5-small"
        gen.device     = "cpu"

    CONTEXT  = "Photosynthesis is the process by which plants convert sunlight into glucose."
    KEYWORD  = "photosynthesis"

    realistic_output = (
        "What process do plants use to convert sunlight into glucose?\n"
        "A. Photosynthesis\nB. Respiration\nC. Fermentation\nD. Digestion"
    )

    # --- on-mode: T5 returns realistic text ---
    with patch.object(gen, "_generate_with_t5", return_value=realistic_output):
        result_on = gen.generate_question(
            context_text=CONTEXT,
            tfidf_keyword=KEYWORD,
            topic="biology",
            bloom_level="understanding",
            difficulty_level="easy",
            question_type="multiple_choice",
            points=1,
        )

    assert result_on is not None, (
        "Expected non-None result when T5 returns realistic MCQ output"
    )
    assert "question_text" in result_on
    assert len(result_on["question_text"]) >= 10

    # --- off-mode: T5 returns None ---
    with patch.object(gen, "_generate_with_t5", return_value=None):
        result_off = gen.generate_question(
            context_text=CONTEXT,
            tfidf_keyword=KEYWORD,
            topic="biology",
            bloom_level="understanding",
            difficulty_level="easy",
            question_type="multiple_choice",
            points=1,
        )

    assert result_off is None, (
        "Expected None result when T5 returns None (generation failure path)"
    )


# ===========================================================================
# Test 4b — T5_on_off_delta (real model — slow)
# ===========================================================================
@pytest.mark.requires_model
def test_T5_on_off_delta_real():
    """
    Real T5 model must either return a valid question dict or None — never crash.
    """
    try:
        from app.exam.t5_generator import T5QuestionGenerator
        gen = T5QuestionGenerator(model_name="t5-small")
    except Exception as exc:
        pytest.skip(f"T5 model load failed: {exc}")

    CONTEXT = "Photosynthesis converts light energy into chemical energy stored in glucose."

    result = gen.generate_question(
        context_text=CONTEXT,
        tfidf_keyword="photosynthesis",
        topic="biology",
        bloom_level="understanding",
        difficulty_level="easy",
        question_type="fill_in_blank",
        points=1,
    )

    # Result is either None (graceful rejection) or a valid question dict
    if result is not None:
        assert "question_text" in result, "Missing question_text key in T5 output"
        assert len(result["question_text"]) >= 10, "question_text too short"


# ===========================================================================
# Test 5 — T5 answerability / toxicity filter (fast)
# ===========================================================================
@pytest.mark.fast
def test_T5_answerability_filter():
    """
    _is_answerable must reject:
      - empty answer
      - fill_in_blank whose answer is absent from context
      - question with < 5 words
      - blank-only question
    And accept a valid fill_in_blank pair.
    """
    with patch("app.exam.t5_generator.logger"):
        from app.exam.t5_generator import T5QuestionGenerator

    with patch.object(T5QuestionGenerator, "__init__", lambda self, model_name=None: None):
        gen = object.__new__(T5QuestionGenerator)

    ctx = "Photosynthesis is the process by which plants produce glucose."

    # Should be answerable
    assert gen._is_answerable(
        "What process produces glucose in plants?", ctx, "photosynthesis", "fill_in_blank"
    ), "Valid answerable question rejected"

    # Empty answer
    assert not gen._is_answerable(
        "What process produces glucose in plants?", ctx, "", "fill_in_blank"
    ), "Empty answer should be unanswerable"

    # Answer not in context
    assert not gen._is_answerable(
        "What process produces glucose in plants?", ctx, "respiration", "fill_in_blank"
    ), "Answer absent from context should be unanswerable"

    # Too short question
    assert not gen._is_answerable(
        "What is it?", ctx, "photosynthesis", "fill_in_blank"
    ), "3-word question should be unanswerable"

    # Blank-only question
    assert not gen._is_answerable(
        "______?", ctx, "photosynthesis", "fill_in_blank"
    ), "Blank-only question should be unanswerable"


@pytest.mark.fast
def test_T5_toxicity_filter():
    """
    _is_toxic must flag known deny-set terms and pass clean text.
    """
    with patch("app.exam.t5_generator.logger"):
        from app.exam.t5_generator import T5QuestionGenerator

    with patch.object(T5QuestionGenerator, "__init__", lambda self, model_name=None: None):
        gen = object.__new__(T5QuestionGenerator)

    assert not gen._is_toxic("What is photosynthesis?"), "Clean text should not be toxic"
    assert not gen._is_toxic(""), "Empty string should not be toxic"
    assert gen._is_toxic("fuck this question"), "Known toxic word should be detected"
    assert gen._is_toxic("What is the role of shit in decomposition?"), "Inline toxic word"
    # True substring inside a longer word should NOT trigger
    assert not gen._is_toxic("The class will study cockpit design principles"), \
        "Substring inside a longer token (cockpit) must not fire"
