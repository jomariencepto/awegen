# app/exam/t5_generator.py

import os
import torch
import random
from transformers import T5ForConditionalGeneration, T5Tokenizer
import json
import re
from nltk.tokenize import word_tokenize
from nltk import pos_tag
from app.utils.logger import get_logger

logger = get_logger(__name__)

# STRICT: Forbidden words that should NEVER appear in generated questions
FORBIDDEN_WORDS = {'one', 'that', 'this', 'to', 'you', 'of'}

T5_MAX_NEW_TOKENS = int(os.getenv("AI_T5_MAX_NEW_TOKENS", "64"))
T5_MAX_INPUT_TOKENS = int(os.getenv("AI_T5_MAX_INPUT_TOKENS", "512"))


class T5QuestionGenerator:
    """
    T5-based question generator for exam system.
    Generates single questions deterministically using T5 encoder-decoder.
    CPU-only, lightweight, no GPU assumptions.
    """
    
    def __init__(self, model_name=None):
        """
        Initialize T5 model and tokenizer.
        Model name resolved from AI_T5_MODEL env var; defaults to t5-small.
        """
        model_name = model_name or os.getenv("AI_T5_MODEL", "t5-small")
        self.model_name = model_name
        self.device = 'cpu'
        
        logger.info(f"Loading T5 model: {model_name} on {self.device}")
        
        try:
            self.tokenizer = T5Tokenizer.from_pretrained(model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            
            logger.info("T5 model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load T5 model: {str(e)}")
            raise
    
    def _construct_prompt(self, context_text, tfidf_keyword, topic, bloom_level, 
                         difficulty_level, question_type):
        """
        Construct T5 input prompt with strict constraints.
        
        Args:
            context_text: Source material text
            tfidf_keyword: Main keyword from TF-IDF
            topic: Subject topic
            bloom_level: Cognitive level (remembering, understanding, etc.)
            difficulty_level: easy, medium, hard
            question_type: multiple_choice, true_false, fill_in_blank, identification
            
        Returns:
            Formatted prompt string for T5
        """
        
        # Clean context to remove forbidden words
        clean_context = self._remove_forbidden_words(context_text[:500])
        
        # Map Bloom level to instruction verb
        bloom_verbs = {
            'remembering': 'define',
            'understanding': 'explain',
            'applying': 'demonstrate',
            'analyzing': 'examine',
            'evaluating': 'assess',
            'creating': 'design'
        }
        
        verb = bloom_verbs.get(bloom_level, 'describe')
        
        quality_rules = (
            "Use only the module context. Do not change the configured question type, "
            "Bloom level, difficulty, time allocation, or coverage. "
            "Do not place the correct answer in the question text. "
            "Do not copy sentences directly from the module. "
            "Write clear academic wording only."
        )

        # Construct type-specific instruction
        if question_type == 'multiple_choice':
            instruction = (
                f"Generate one multiple choice question whose correct answer is the target concept "
                f"'{tfidf_keyword}'. Ask students to {verb} the concept without naming it in the stem. "
                f"Provide exactly 4 options labeled A-D with 1 correct answer and 3 plausible distractors."
            )
        elif question_type == 'true_false':
            instruction = (
                f"Generate one true/false statement about the target concept '{tfidf_keyword}'. "
                f"Base it strictly on the module context."
            )
        elif question_type == 'fill_in_blank':
            instruction = (
                f"Generate one fill-in-the-blank question whose answer is '{tfidf_keyword}'. "
                f"Use ______ for the blank and do not reveal the answer in the question text."
            )
        elif question_type == 'identification':
            instruction = (
                f"Generate one identification question whose correct answer is '{tfidf_keyword}'. "
                f"Ask students to {verb} the concept without naming it in the prompt."
            )
        else:
            instruction = f"Generate a question about {tfidf_keyword}."
        
        # Add difficulty hint
        difficulty_hints = {
            'easy': 'Make it straightforward.',
            'medium': 'Make it moderately challenging.',
            'hard': 'Make it complex and analytical.'
        }
        
        difficulty_hint = difficulty_hints.get(difficulty_level, '')
        
        # Final prompt
        prompt = f"{instruction} {quality_rules} {difficulty_hint} Context: {clean_context}"
        
        return prompt
    
    def _remove_forbidden_words(self, text):
        """
        Remove forbidden words from text.
        
        Args:
            text: Input text
            
        Returns:
            Cleaned text without forbidden words
        """
        if not text:
            return text
        
        words = text.split()
        filtered_words = [w for w in words if w.lower() not in FORBIDDEN_WORDS]
        
        return ' '.join(filtered_words)
    
    def _contains_forbidden_words(self, text):
        """
        Check if text contains forbidden words.
        
        Args:
            text: Text to check
            
        Returns:
            Boolean indicating presence of forbidden words
        """
        if not text:
            return False
        
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        return any(word in FORBIDDEN_WORDS for word in words)
    

    
    def _humanize_question_text(self, text):
        """
        NEW: Humanize generated questions to sound more teacher-like and less AI-generated.
        """
        if not text:
            return text
        
        # Remove overly formal language
        formal_to_casual = {
            'utilize': 'use',
            'implement': 'set up',
            'demonstrate': 'show',
            'indicate': 'show',
            'represents': 'is',
            'provides': 'gives',
            'enables': 'allows',
            'facilitates': 'helps with',
            'comprises': 'includes',
            'encompasses': 'covers'
        }
        
        text_lower = text.lower()
        for formal, casual in formal_to_casual.items():
            if formal in text_lower:
                # Replace with case sensitivity
                pattern = re.compile(re.escape(formal), re.IGNORECASE)
                text = pattern.sub(casual, text, count=1)
        
        # Add natural variations to question starters
        if text.startswith('What is the'):
            if random.random() < 0.5:
                text = text.replace('What is the', "What's the", 1)
        
        # Make questions sound more conversational
        conversational_tweaks = [
            ('Which of the following', 'Which'),
            ('Select the correct', 'What is the correct'),
            ('Identify the', 'What is the'),
            ('The following', 'The')
        ]
        
        for old_phrase, new_phrase in conversational_tweaks:
            if old_phrase in text:
                text = text.replace(old_phrase, new_phrase, 1)
                break
        
        return text

    # ------------------------------------------------------------------
    # Feature 3: Toxicity / Answerability filters
    # ------------------------------------------------------------------

    _TOXIC_DENY_SET = frozenset({
        'fuck', 'fucking', 'shit', 'bitch', 'bastard', 'asshole',
        'cunt', 'dick', 'cock', 'pussy', 'whore', 'nigger', 'nigga',
        'faggot', 'retard',
    })

    def _is_toxic(self, text: str) -> bool:
        """
        Return True if *text* contains a whole-word match from the deny-set.
        No external library required — word-boundary regex only.
        """
        if not text:
            return False
        tl = text.lower()
        return any(
            re.search(r'\b' + re.escape(term) + r'\b', tl)
            for term in self._TOXIC_DENY_SET
        )

    def _is_answerable(self, question_text: str, context_text: str,
                       correct_answer, question_type: str) -> bool:
        """
        Return True when the question is considered answerable:
        1. Answer must be non-empty.
        2. For fill_in_blank / identification: answer must appear in context text.
        3. Question must contain >= 5 words.
        4. Question must not consist entirely of blanks (e.g. "______?").
        """
        # Rule 1: answer must exist
        if not correct_answer or not str(correct_answer).strip():
            return False

        # Rule 2: answer must be traceable in context for extractive types
        if question_type in ('fill_in_blank', 'identification'):
            if context_text and str(correct_answer).lower() not in context_text.lower():
                return False

        # Rule 3: question must have substance
        if len(question_text.split()) < 5:
            return False

        # Rule 4: reject blank-only questions
        stripped = re.sub(r'_+', '', question_text).strip().rstrip('?').strip()
        if not stripped:
            return False

        return True

    def _generate_with_t5(self, prompt, max_length=150, temperature=0.7, num_beams=4):
        """
        Call T5 model to generate text.
        
        Args:
            prompt: Input prompt for T5
            max_length: Maximum output length
            temperature: Sampling temperature
            num_beams: Beam search width
            
        Returns:
            Generated text string
        """
        try:
            # Tokenize input
            inputs = self.tokenizer(
                prompt,
                return_tensors='pt',
                max_length=T5_MAX_INPUT_TOKENS,
                truncation=True
            ).to(self.device)
            
            # Generate with controlled parameters
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs['input_ids'],
                    max_length=min(max_length, T5_MAX_NEW_TOKENS),
                    temperature=temperature,
                    num_beams=num_beams,
                    early_stopping=True,
                    do_sample=True if temperature > 0 else False,
                    top_k=50,
                    top_p=0.95,
                    repetition_penalty=1.2
                )
            
            # Decode output
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"T5 generation failed: {str(e)}")
            return None

    def _parse_multiple_choice(self, generated_text, tfidf_keyword):
        """
        Parse multiple choice question from T5 output.
        
        Args:
            generated_text: Raw T5 output
            tfidf_keyword: Keyword for fallback option generation
            
        Returns:
            Tuple of (question_text, options_list, correct_answer)
        """
        # Extract question text (before options)
        question_match = re.search(r'^(.*?)(?=\n[A-D]\.|\n\d\.)', generated_text, re.DOTALL)
        question_text = question_match.group(1).strip() if question_match else generated_text.split('\n')[0]
        
        # Extract options
        option_pattern = r'(?:^|\n)([A-D])\.\s*(.+?)(?=\n[A-D]\.|$)'
        options_matches = re.findall(option_pattern, generated_text, re.MULTILINE | re.DOTALL)
        
        if len(options_matches) >= 4:
            options = [match[1].strip() for match in options_matches[:4]]
            # Try to find an explicit answer marker in the T5 output (e.g. "Answer: B")
            answer_match = re.search(
                r'(?:Answer|Correct(?:\s+Answer)?)\s*[:\-]\s*([A-D])',
                generated_text, re.IGNORECASE
            )
            if answer_match:
                letter = answer_match.group(1).upper()
                idx = ord(letter) - ord('A')
                correct_answer = options[idx] if 0 <= idx < len(options) else options[0]
            else:
                # Fallback: pick the option whose text contains the tfidf_keyword
                keyword_lower = tfidf_keyword.lower()
                correct_answer = next(
                    (opt for opt in options if keyword_lower in opt.lower()),
                    options[0]
                )
        else:
            # Fallback: Generate generic options
            options = [
                f"{tfidf_keyword} represents the primary concept",
                f"{tfidf_keyword} indicates a secondary element",
                f"{tfidf_keyword} describes an alternative approach",
                f"{tfidf_keyword} suggests a different framework"
            ]
            correct_answer = options[0]
        
        return question_text, options, correct_answer
    
    def _parse_true_false(self, generated_text):
        """
        Parse true/false question from T5 output.
        
        Args:
            generated_text: Raw T5 output
            
        Returns:
            Tuple of (statement, correct_answer)
        """
        # Clean statement
        statement = generated_text.strip()
        
        # Remove any True/False labels if present
        statement = re.sub(r'\b(True|False)\b', '', statement, flags=re.IGNORECASE).strip()
        
        # Ensure statement ends with period
        if not statement.endswith('.'):
            statement += '.'
        
        # POS-aware negation detection — check if negation modifies the
        # main predicate (not a subordinate clause or quoted text).
        has_main_negation = False
        try:
            tagged = pos_tag(word_tokenize(statement.lower()))
            negation_tokens = {'not', "n't", 'never', 'neither', 'nor', 'cannot', 'no'}
            for i, (word, tag) in enumerate(tagged):
                if word in negation_tokens:
                    # Negation adjacent to a verb → main predicate negation
                    if i + 1 < len(tagged) and tagged[i + 1][1].startswith('VB'):
                        has_main_negation = True
                        break
                    if i > 0 and tagged[i - 1][1] in ('MD', 'VBZ', 'VBP', 'VBD', 'VB'):
                        has_main_negation = True
                        break
                    # Standalone negation words like "incorrect", "false"
                    if word in ('incorrect', 'false', 'never', 'neither'):
                        has_main_negation = True
                        break
        except Exception:
            # Fallback to simple keyword check
            negation_words = ['not', 'never', 'cannot', 'incorrect', 'false']
            has_main_negation = any(w in statement.lower() for w in negation_words)

        correct_answer = 'False' if has_main_negation else 'True'
        
        return statement, correct_answer
    
    def _parse_fill_in_blank(self, generated_text, tfidf_keyword):
        """
        Parse fill-in-the-blank question from T5 output.
        
        Args:
            generated_text: Raw T5 output
            tfidf_keyword: Keyword to use as correct answer if not found
            
        Returns:
            Tuple of (question_text, correct_answer)
        """
        # Ensure blank marker exists
        if '______' not in generated_text:
            # Insert blank before keyword if present
            if tfidf_keyword.lower() in generated_text.lower():
                generated_text = generated_text.replace(
                    tfidf_keyword, 
                    '______', 
                    1
                )
            else:
                # POS-aware blank selection: blank the first noun (> 3 chars)
                # instead of the arbitrary middle word.
                words = generated_text.split()
                blanked = False
                if len(words) > 5:
                    try:
                        tagged = pos_tag(words)
                        for i, (word, tag) in enumerate(tagged):
                            if tag.startswith('NN') and len(word) > 3 and 0 < i < len(words) - 1:
                                tfidf_keyword = word  # use blanked word as answer
                                words[i] = '______'
                                blanked = True
                                break
                    except Exception:
                        pass
                    if not blanked:
                        words[len(words) // 2] = '______'
                    generated_text = ' '.join(words)
        
        question_text = generated_text.strip()
        
        # Extract correct answer (use keyword as fallback)
        correct_answer = tfidf_keyword
        
        return question_text, correct_answer
    
    def _parse_identification(self, generated_text, tfidf_keyword):
        """
        Parse identification question from T5 output.
        
        Args:
            generated_text: Raw T5 output
            tfidf_keyword: Keyword to use as correct answer
            
        Returns:
            Tuple of (question_text, correct_answer)
        """
        question_text = generated_text.strip()
        
        # Ensure it ends with question mark
        if not question_text.endswith('?'):
            question_text += '?'
        
        # Use keyword as correct answer
        correct_answer = tfidf_keyword
        
        return question_text, correct_answer
    
    def generate_question(self, context_text, tfidf_keyword, topic, bloom_level, 
                         difficulty_level, question_type, points):
        """
        Generate a single exam question using T5.
        
        Args:
            context_text: Source material (string)
            tfidf_keyword: Main keyword from TF-IDF (string)
            topic: Subject topic (string)
            bloom_level: Cognitive level (string)
            difficulty_level: easy, medium, hard (string)
            question_type: Type of question (string)
            points: Point value (integer)
            
        Returns:
            Dictionary matching ExamQuestion schema or None if generation fails
        """
        try:
            # Construct prompt
            prompt = self._construct_prompt(
                context_text, tfidf_keyword, topic, bloom_level, 
                difficulty_level, question_type
            )
            
            logger.info(f"Generating {question_type} question for keyword: {tfidf_keyword}")
            
            # Generate with T5
            generated_text = self._generate_with_t5(prompt)
            
            if not generated_text:
                logger.warning("T5 generation returned empty result")
                return None
            
            # Check for forbidden words in output
            if self._contains_forbidden_words(generated_text):
                logger.warning("Generated text contains forbidden words, filtering...")
                generated_text = self._remove_forbidden_words(generated_text)
            
            # Parse based on question type
            if question_type == 'multiple_choice':
                question_text, options, correct_answer = self._parse_multiple_choice(
                    generated_text, tfidf_keyword
                )
            elif question_type == 'true_false':
                question_text, correct_answer = self._parse_true_false(generated_text)
                options = None
            elif question_type == 'fill_in_blank':
                question_text, correct_answer = self._parse_fill_in_blank(
                    generated_text, tfidf_keyword
                )
                options = None
            elif question_type == 'identification':
                question_text, correct_answer = self._parse_identification(
                    generated_text, tfidf_keyword
                )
                options = None
            else:
                logger.warning(f"Unknown question type: {question_type}")
                return None

            # Feature 3: answerability + toxicity gates
            if not self._is_answerable(question_text, context_text, correct_answer, question_type):
                logger.warning(f"T5 output rejected (unanswerable) type='{question_type}' "
                               f"keyword='{tfidf_keyword}'")
                return None
            if self._is_toxic(question_text) or self._is_toxic(str(correct_answer or '')):
                logger.warning("T5 output rejected (toxic content)")
                return None

            # Final validation
            if not question_text or len(question_text) < 10:
                logger.warning("Question text too short or empty")
                return None

            if question_type in ('multiple_choice', 'fill_in_blank', 'identification'):
                answer_text = str(correct_answer or '').strip()
                if answer_text and re.search(re.escape(answer_text), question_text, re.IGNORECASE):
                    logger.warning("Question text exposes the correct answer")
                    return None

            if question_type == 'multiple_choice':
                if not isinstance(options, list) or len(options) != 4 or len(set(options)) != 4:
                    logger.warning("MCQ must contain exactly 4 distinct options")
                    return None
                if correct_answer not in options:
                    logger.warning("MCQ correct answer must be included in options")
                    return None
             
            if self._contains_forbidden_words(question_text):
                logger.warning("Question text still contains forbidden words after filtering")
                return None
            
            # NEW: Humanize question text
            question_text = self._humanize_question_text(question_text)
            
            # Construct output JSON
            output = {
                'question_text': question_text,
                'options': options,
                'correct_answer': correct_answer,
                'question_type': question_type,
                'difficulty_level': difficulty_level,
                'bloom_level': bloom_level,
                'topic': topic,
                'points': points
            }
            
            logger.info(f"Successfully generated {question_type} question")
            
            return output
            
        except Exception as e:
            logger.error(f"Error generating question: {str(e)}")
            return None
    
    def generate_batch(self, generation_specs):
        """
        Generate multiple questions from a list of specifications.
        
        Args:
            generation_specs: List of dicts, each containing:
                - context_text
                - tfidf_keyword
                - topic
                - bloom_level
                - difficulty_level
                - question_type
                - points
                
        Returns:
            List of generated question dictionaries
        """
        questions = []
        
        for spec in generation_specs:
            question = self.generate_question(
                context_text=spec['context_text'],
                tfidf_keyword=spec['tfidf_keyword'],
                topic=spec['topic'],
                bloom_level=spec['bloom_level'],
                difficulty_level=spec['difficulty_level'],
                question_type=spec['question_type'],
                points=spec['points']
            )
            
            if question:
                questions.append(question)
        
        logger.info(f"Generated {len(questions)} questions from {len(generation_specs)} specs")
        
        return questions
