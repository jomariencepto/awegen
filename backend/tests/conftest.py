"""
tests/conftest.py

Shared pytest fixtures for the AI sanity suite.

No Flask app context, MySQL, Redis, or Celery is required here.
All database interaction is mocked via MagicMock.
"""
import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Text fixtures
# ---------------------------------------------------------------------------

SAMPLE_TEXT = """\
Machine learning is a branch of artificial intelligence and computer science.
Supervised learning algorithms learn from labelled training data to make predictions.
Neural networks are inspired by the structure of biological neurons in the brain.
Deep learning uses multiple hidden layers in neural networks to extract features.
Gradient descent optimisation adjusts model weights to minimise the loss function.
Convolutional neural networks are particularly effective for image classification tasks.
Recurrent neural networks process sequential data such as text and time series.
Transformer architecture introduced self-attention mechanisms for natural language processing.
Backpropagation calculates gradients for training neural networks efficiently.
Overfitting occurs when a model memorises training data and fails to generalise.
Regularisation techniques such as dropout and weight decay reduce overfitting.
Cross-validation is used to evaluate the generalisation performance of a model.
Transfer learning reuses pretrained model weights for new downstream tasks.
Hyperparameter tuning searches for optimal configuration values for a model.
Feature engineering transforms raw data into informative representations for models.
""".strip()

SAMPLE_ENTITY_TEXT = (
    "Albert Einstein developed the theory of relativity while working in Germany. "
    "Google was founded in September 1998 by Larry Page and Sergey Brin. "
    "The United Nations was established in New York after World War II. "
    "Apple Inc. released the first iPhone in January 2007 in San Francisco."
)

# 10 sentences; items at indices 1, 4, and 6 are near-duplicates of 0, 3, and 5
SAMPLE_SENTENCES_WITH_DUPES = [
    "Machine learning is a subset of artificial intelligence.",           # 0
    "Machine learning is a subset of artificial intelligence.",           # 1 exact dup of 0
    "Machine learning is a branch of artificial intelligence.",           # 2 near-dup of 0
    "Deep learning uses multiple layers in neural networks.",             # 3
    "Deep learning leverages multiple hidden layers in neural networks.", # 4 near-dup of 3
    "Gradient descent minimises the loss function during training.",      # 5
    "Gradient descent is used to minimise the loss function in training.",# 6 near-dup of 5
    "Backpropagation is used to train neural networks.",                  # 7
    "Transfer learning reuses pretrained model weights.",                 # 8
    "Feature engineering creates informative representations from data.", # 9
]


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_text():
    return SAMPLE_TEXT


@pytest.fixture
def sample_entity_text():
    return SAMPLE_ENTITY_TEXT


@pytest.fixture
def sample_sentences_with_dupes():
    return SAMPLE_SENTENCES_WITH_DUPES


@pytest.fixture
def mock_db_session():
    """SQLAlchemy session mock that silently accepts add/commit/rollback calls."""
    session = MagicMock()
    session.add      = MagicMock()
    session.commit   = MagicMock()
    session.rollback = MagicMock()
    return session
