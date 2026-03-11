import re
import string
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.stem import WordNetLemmatizer
from nltk import pos_tag
from nltk.corpus import wordnet
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TextCleaner:
    def __init__(self):
        # Keep existing behavior, but make it robust if NLTK data isn't downloaded yet
        try:
            self.stop_words = set(stopwords.words("english"))
        except Exception as e:
            logger.warning(f"NLTK stopwords not available ({e}). Using empty stopword set.")
            self.stop_words = set()

        self.lemmatizer = WordNetLemmatizer()

    # ------------------------------------------------------------------
    # POS-aware lemmatization (maps Penn Treebank tags → WordNet POS)
    # ------------------------------------------------------------------
    @staticmethod
    def _get_wordnet_pos(treebank_tag):
        if treebank_tag.startswith('J'):
            return wordnet.ADJ
        elif treebank_tag.startswith('V'):
            return wordnet.VERB
        elif treebank_tag.startswith('R'):
            return wordnet.ADV
        return wordnet.NOUN  # default — nouns are the most common

    # ---------------------------------------------------------------------
    # FIX: This method was incorrectly indented inside extract_paragraphs().
    # Also FIX: previous regex removed spaces between ANY letters which can
    # destroy normal text. This version only de-spaces "E x p l a i n" style.
    # ---------------------------------------------------------------------
    def normalize_spaced_text(self, text: str) -> str:
        if not text:
            return ""

        # Type-2 artifact: space-per-character runs, e.g. "E x p l a i n" -> "Explain"
        # Require 4+ letters to avoid damaging normal text like "I am"
        def _despace_run(match):
            return match.group(0).replace(" ", "")

        text = re.sub(r'(?<!\w)(?:[A-Za-z]\s){3,}[A-Za-z](?!\w)', _despace_run, text)

        # Type-1 artifact: newline-per-character (common in OCR/PDF)
        # Example:
        #   E\nx\np\nl\na\ni\nn\n -> Explain
        # We join sequences of single-letter lines into words.
        lines = text.splitlines()
        if lines:
            rebuilt = []
            buf = []
            # If a large portion of lines are single letters, treat as artifact
            single_letter_lines = sum(1 for ln in lines if len(ln.strip()) == 1 and ln.strip().isalpha())
            if len(lines) >= 10 and (single_letter_lines / max(len(lines), 1)) > 0.35:
                for ln in lines:
                    s = ln.strip()
                    if len(s) == 1 and s.isalpha():
                        buf.append(s)
                        continue

                    # flush buffer
                    if buf:
                        rebuilt.append("".join(buf))
                        buf = []

                    if s:
                        rebuilt.append(s)

                if buf:
                    rebuilt.append("".join(buf))

                text = " ".join(rebuilt)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def clean_text(self, text):
        text = self.normalize_spaced_text(text)
        try:
            # Convert to lowercase
            text = text.lower()

            # Remove special characters and numbers
            text = re.sub(r"[^a-zA-Z\s]", "", text)

            # Remove extra whitespace
            text = re.sub(r"\s+", " ", text).strip()

            # Tokenize and POS-tag for accurate lemmatization
            tokens = word_tokenize(text)
            tagged = pos_tag(tokens)

            # Remove stopwords and lemmatize (produces real words, not stems)
            cleaned_tokens = [
                self.lemmatizer.lemmatize(token, self._get_wordnet_pos(tag))
                for token, tag in tagged
                if token not in self.stop_words and len(token) > 2
            ]

            return " ".join(cleaned_tokens)
        except Exception as e:
            logger.error(f"Error cleaning text: {str(e)}")
            return text

    def clean_text_for_tfidf(self, text):
        """
        Clean text specifically for TF-IDF while preserving important terms.
        Less aggressive than clean_text() - preserves technical terms.
        """
        text = self.normalize_spaced_text(text)
        try:
            # Convert to lowercase
            text = text.lower()

            # Remove URLs
            text = re.sub(r"http\S+|www\S+", "", text)

            # Remove email addresses
            text = re.sub(r"\S+@\S+", "", text)

            # Keep alphanumeric and underscores; replace punctuation with space
            # (preserves snake_case and numbers inside terms; avoids gluing tokens)
            text = re.sub(r"[^\w\s]", " ", text)

            # Remove extra whitespace
            text = re.sub(r"\s+", " ", text).strip()

            # Tokenize
            tokens = word_tokenize(text)

            # Remove stopwords but keep longer tokens (technical terms)
            # Don't stem - preserve original terms for TF-IDF
            cleaned_tokens = [
                token
                for token in tokens
                if (token not in self.stop_words and len(token) > 2) or len(token) > 4
            ]

            return " ".join(cleaned_tokens)
        except Exception as e:
            logger.error(f"Error cleaning text for TF-IDF: {str(e)}")
            return text

    def extract_sentences(self, text):
        try:
            text = self.normalize_spaced_text(text)
            # Use NLTK Punkt tokenizer — handles abbreviations (Dr., e.g., U.S.),
            # decimal numbers (1.5), and other edge cases correctly.
            sentences = sent_tokenize(text)
            return [s.strip() for s in sentences if s.strip()]
        except Exception as e:
            logger.error(f"Error extracting sentences: {str(e)}")
            return [text]

    def extract_paragraphs(self, text):
        try:
            text = self.normalize_spaced_text(text)
            # Split text into paragraphs
            paragraphs = re.split(r"\n\s*\n", text)
            return [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]
        except Exception as e:
            logger.error(f"Error extracting paragraphs: {str(e)}")
            return [text]