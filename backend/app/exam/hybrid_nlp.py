import random
import re
from collections import defaultdict
from nltk.tokenize import sent_tokenize
from app.exam.tfidf_engine import TFIDFEngine
from app.utils.logger import get_logger
from app.exam.bloom_classifier import BloomClassifier

logger = get_logger(__name__)

# STRICT: Forbidden words that should NEVER appear in generated questions
FORBIDDEN_WORDS = {'one', 'that', 'this', 'to', 'you', 'of', 'the', 'a', 'an'}


class HybridNLPEngine:
    """
    IMPROVED: Enhanced humanized exam question generation with:
    - Better answer leakage prevention
    - Context-aware question generation
    - Improved distractor generation
    - Quality validation
    """
    
    def __init__(self):
        self.tfidf_engine = TFIDFEngine()
        self.bloom_classifier = BloomClassifier()
        self.generated_questions = set()
        self.question_variations = defaultdict(int)
        self.used_keywords = set()
        
        # IMPROVED: Enhanced humanized question templates with context placeholders
        self.humanized_templates = {
            'multiple_choice': {
                'remembering': [
                    "Which {item_type} handles {function}?",
                    "What's the main {concept_type} used in {domain}?",
                    "Can you identify the {component_type} that performs {purpose}?",
                    "What {element_type} do we use for {application}?",
                    "Which {mechanism_type} is responsible for {operation}?"
                ],
                'understanding': [
                    "How would you explain how {system} achieves {purpose}?",
                    "What's the relationship between {element_a} and {element_b}?",
                    "Which principle best explains {behavior} in {context}?",
                    "Can you describe the role of {function} within {framework}?",
                    "Why does {condition} happen in {system}?"
                ],
                'applying': [
                    "In {scenario}, which approach would work best for {goal}?",
                    "When you're implementing {task}, what helps ensure {outcome}?",
                    "How would you use {concept} to solve {problem}?",
                    "Show how you'd apply {tool} for {purpose}.",
                    "Which technique would you use to address {challenge} in {context}?"
                ],
                'analyzing': [
                    "How does {component} affect {outcome} in {system}?",
                    "What's the difference between using {method_a} versus {method_b}?",
                    "What makes {approach_a} different from {approach_b}?",
                    "What happens to the system when {condition} changes?",
                    "How are {element_a} and {element_b} related?"
                ],
                'evaluating': [
                    "Which strategy works best for achieving {objective}?",
                    "How effective is {method} for {purpose}?",
                    "Is {approach} appropriate in {context}?",
                    "What are the limitations of {solution} compared to {alternative}?",
                    "Why would {option} be better for {scenario}?"
                ],
                'creating': [
                    "How would you design something that combines {element_a} and {element_b}?",
                    "What solution would you propose for {challenge} using {principle}?",
                    "How would you create a strategy that integrates {concept} within {framework}?",
                    "Can you develop a method for implementing {functionality}?",
                    "What approach would enhance {outcome} through {technique}?"
                ]
            }
        }
        
        # NEW: Natural conversation starters to make questions feel more authentic
        self.conversation_starters = [
            "", # Sometimes no starter is best
            "In practice, ",
            "Consider this: ",
            "Think about ",
            "Let's say ",
            "Suppose ",
            "Imagine ",
            "In real-world scenarios, ",
        ]
        
        # NEW: Natural question connectors for better flow
        self.question_connectors = [
            "which means",
            "which indicates",
            "suggesting that",
            "implying",
            "showing",
            "demonstrating"
        ]
        
        # NEW: Casual rephrasing patterns to make questions sound more natural
        self.natural_rephrasing = {
            "is responsible for": ["handles", "takes care of", "manages", "is used for"],
            "represents": ["is", "stands for", "means", "refers to"],
            "identify": ["can you identify", "what is", "find", "name"],
            "select": ["choose", "pick", "identify", "what is"],
            "manages": ["handles", "controls", "oversees", "deals with"],
            "achieve": ["accomplish", "reach", "get", "attain"],
            "explains": ["shows", "demonstrates", "illustrates", "describes"],
            "underlies": ["is behind", "explains", "causes", "supports"],
            "explain": ["describe", "tell me about", "can you explain", "what's"],
            "occur": ["happen", "take place", "come about", "arise"],
            "accomplishes": ["achieves", "gets done", "completes", "finishes"],
            "ensures": ["makes sure", "guarantees", "provides", "gives"],
            "demonstrate": ["show", "illustrate", "explain", "describe"],
            "addresses": ["solves", "handles", "deals with", "fixes"],
            "examine": ["look at", "consider", "analyze", "study"],
            "influences": ["affects", "impacts", "changes", "alters"],
            "compare": ["what's the difference between", "contrast", "how do", "which is better"],
            "distinguishes": ["makes different", "sets apart", "differentiates", "separates"],
            "analyze": ["look at", "examine", "study", "consider"],
            "investigate": ["look into", "examine", "study", "explore"],
            "assess": ["evaluate", "judge", "determine", "figure out"],
            "evaluate": ["assess", "judge", "rate", "measure"],
            "judge": ["determine", "decide", "evaluate", "assess"],
            "critique": ["evaluate", "assess", "review", "analyze"],
            "justify": ["explain why", "give reasons for", "show why", "prove"],
            "proves": ["is", "shows to be", "demonstrates as", "turns out to be"],
            "design": ["create", "develop", "build", "make"],
            "propose": ["suggest", "recommend", "offer", "present"],
            "formulate": ["create", "develop", "design", "build"],
            "construct": ["build", "create", "develop", "make"],
            "develop": ["create", "build", "design", "make"]
        }
        
        self.stop_words = {

            # Articles
            'the', 'a', 'an',

            # Conjunctions
            'and', 'or', 'but', 'so',

            # Prepositions
            'in', 'on', 'at', 'for', 'with', 'by', 'of', 'to',

            # Auxiliary / linking verbs
            'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had',
            'do', 'does', 'did',

            # Demonstratives (optional — keep if meaning matters)
            'this', 'that', 'these', 'those',

            # Other common fillers
            'one'
        }
        
        # IMPROVED: Context-aware replacement mappings
        self.context_replacements = {
            'command': ['utility', 'tool', 'function', 'program', 'operation'],
            'file': ['resource', 'document', 'item', 'object', 'entity'],
            'process': ['operation', 'procedure', 'method', 'technique', 'approach'],
            'concept': ['principle', 'idea', 'element', 'component', 'aspect'],
            'system': ['framework', 'structure', 'mechanism', 'architecture', 'platform'],
            'data': ['information', 'content', 'material', 'input', 'output'],
            'function': ['capability', 'feature', 'operation', 'service', 'functionality']
        }
    
    def reset_generated_questions(self):
        """Reset the set of generated questions to allow fresh generation."""
        self.generated_questions = set()
        self.question_variations = defaultdict(int)
        self.used_keywords = set()
    
    def _contains_forbidden_words(self, text):
        """Check if text contains any forbidden words."""
        if not text:
            return False
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        return any(word in FORBIDDEN_WORDS for word in words)
    
    def _extract_concept_placeholder(self, text):
        """Extract concept placeholders from abstracted text."""
        pattern = r'<concept:([^>]+)>'
        matches = re.findall(pattern, text)
        return matches if matches else []
    
    def _detect_question_context(self, text, keyword):
        """
        IMPROVED: Detect the context of the question for better replacement selection.
        """
        text_lower = text.lower()
        keyword_lower = keyword.lower()
        
        # Context detection patterns
        if any(word in text_lower for word in ['execute', 'run', 'perform', 'invoke']):
            return 'command'
        elif any(word in text_lower for word in ['save', 'load', 'read', 'write', 'open']):
            return 'file'
        elif any(word in text_lower for word in ['calculate', 'compute', 'process', 'transform']):
            return 'process'
        elif any(word in text_lower for word in ['define', 'explain', 'describe', 'concept']):
            return 'concept'
        elif any(word in text_lower for word in ['manage', 'control', 'coordinate', 'organize']):
            return 'system'
        elif any(word in text_lower for word in ['store', 'retrieve', 'contain', 'hold']):
            return 'data'
        elif any(word in text_lower for word in ['provide', 'enable', 'allow', 'support']):
            return 'function'
        
        return 'concept'  # Default fallback
    
    def _extract_context_metadata(self, abstracted_text, keyword):
        """
        IMPROVED: Extract enhanced contextual metadata from abstracted text.
        """
        metadata = {
            'item_type': 'element',
            'function': 'processing operations',
            'concept_type': 'mechanism',
            'domain': 'the system',
            'component_type': 'component',
            'purpose': 'managing tasks',
            'element_type': 'feature',
            'application': 'handling operations',
            'mechanism_type': 'process',
            'operation': 'execution',
            'system': 'the framework',
            'element_a': 'input',
            'element_b': 'output',
            'behavior': 'functionality',
            'context': 'this environment',
            'framework': 'system structure',
            'scenario': 'practical situations',
            'goal': 'desired outcomes',
            'task': 'required operations',
            'outcome': 'results',
            'concept': 'underlying principles',
            'problem': 'challenges',
            'tool': 'available resources',
            'challenge': 'difficulties',
            'component': 'key parts',
            'method_a': 'approach one',
            'method_b': 'approach two',
            'approach_a': 'method one',
            'approach_b': 'method two',
            'condition': 'specific circumstances',
            'objective': 'target goals',
            'method': 'systematic approaches',
            'approach': 'strategies',
            'solution': 'responses',
            'alternative': 'other options',
            'option': 'choices',
            'principle': 'fundamental rules',
            'functionality': 'operational capabilities',
            'technique': 'specialized methods'
        }
        
        # IMPROVED: Dynamic metadata extraction from context
        if abstracted_text:
            text_lower = abstracted_text.lower()
            
            # Detect specific patterns
            if 'display' in text_lower or 'show' in text_lower or 'output' in text_lower:
                metadata['function'] = 'displaying information'
                metadata['purpose'] = 'presenting data'
            
            if 'combine' in text_lower or 'merge' in text_lower or 'concatenate' in text_lower:
                metadata['function'] = 'combining elements'
                metadata['purpose'] = 'integrating components'
            
            if 'file' in text_lower or 'document' in text_lower:
                metadata['domain'] = 'file operations'
                metadata['context'] = 'file management systems'
                metadata['item_type'] = 'resource'
            
            if 'command' in text_lower or 'utility' in text_lower or 'tool' in text_lower:
                metadata['system'] = 'command-line interface'
                metadata['item_type'] = 'utility'
                metadata['component_type'] = 'command'
            
            if 'process' in text_lower or 'execute' in text_lower:
                metadata['purpose'] = 'executing operations'
                metadata['function'] = 'processing tasks'
            
            if 'data' in text_lower or 'information' in text_lower:
                metadata['domain'] = 'data management'
                metadata['item_type'] = 'data structure'
            
            # Extract verbs for dynamic function/purpose
            verbs = re.findall(r'\b(manage|control|handle|process|execute|display|store|retrieve|calculate|transform|coordinate)\w*\b', text_lower)
            if verbs:
                metadata['function'] = f"{verbs[0]}ing operations"
        
        return metadata
    
    def generate_humanized_mcq(self, abstracted_text, keyword, keyword_map, bloom_level, difficulty, points):
        """
        IMPROVED: Generate a humanized MCQ with enhanced answer leakage prevention.
        """
        try:
            # Detect context for this keyword
            context_type = self._detect_question_context(abstracted_text, keyword)
            
            # Extract enhanced metadata
            metadata = self._extract_context_metadata(abstracted_text, keyword)
            
            # Get template
            templates = self.humanized_templates['multiple_choice'].get(bloom_level, 
                         self.humanized_templates['multiple_choice']['remembering'])
            template = random.choice(templates)
            
            # Build question stem WITHOUT the answer keyword
            question_text = template.format(**metadata)
            
            # IMPROVED: Enhanced answer leakage prevention
            question_text = self._ensure_no_answer_leakage(question_text, keyword, context_type)
            
            # Polish question
            question_text = self._polish_question_text(question_text)
            
            # Validate no forbidden words
            if self._contains_forbidden_words(question_text):
                logger.warning(f"Question contains forbidden words: {question_text}")
                return None
            
            # IMPROVED: Generate better distractors
            distractors = self._generate_contextual_distractors(
                keyword, abstracted_text, keyword_map, context_type
            )
            
            if len(distractors) < 3:
                logger.warning(f"Insufficient distractors for keyword: {keyword}")
                return None
            
            # Build options
            options = [keyword] + distractors[:3]
            random.shuffle(options)
            
            # Final validation: ensure question doesn't contain any option
            for option in options:
                if option.lower() in question_text.lower():
                    logger.warning(f"Question contains option '{option}': {question_text}")
                    return None
            
            # Additional validation: ensure options are distinct
            if len(set([opt.lower() for opt in options])) < 4:
                logger.warning(f"Duplicate options detected: {options}")
                return None
            
            return {
                'question': question_text,
                'options': options,
                'answer': keyword,
                'difficulty': difficulty,
                'bloom_level': bloom_level,
                'points': points,
                'question_type': 'multiple_choice'
            }
            
        except Exception as e:
            logger.error(f"Error generating humanized MCQ: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _ensure_no_answer_leakage(self, question_text, answer, context_type):
        """
        IMPROVED: Enhanced answer leakage prevention with context-aware replacements.
        """
        # Check if answer appears in question
        if answer.lower() in question_text.lower():
            # Get context-appropriate replacements
            replacements = self.context_replacements.get(context_type, ['element', 'component', 'entity'])
            
            # Select random replacement for variety
            replacement = random.choice(replacements)
            
            # Replace answer with generic term
            question_text = re.sub(
                r'\b' + re.escape(answer) + r'\b', 
                replacement, 
                question_text, 
                flags=re.IGNORECASE
            )
            
            logger.info(f"Replaced '{answer}' with '{replacement}' in question")
        
        return question_text
    
    def _generate_contextual_distractors(self, correct_answer, context, keyword_map, context_type):
        """
        IMPROVED: Generate highly plausible, contextually relevant distractors.
        """
        distractors = []
        
        # Strategy 1: Use other keywords from the same context (IMPROVED)
        available_keywords = [
            kw for placeholder, kw in keyword_map.items() 
            if kw != correct_answer and len(kw) > 2 and kw.lower() != correct_answer.lower()
        ]
        
        # Filter keywords by context similarity
        context_keywords = []
        for kw in available_keywords:
            kw_context = self._detect_question_context(context, kw)
            if kw_context == context_type:
                context_keywords.append(kw)
        
        # Use context-similar keywords first
        if context_keywords:
            distractors.extend(random.sample(context_keywords, min(2, len(context_keywords))))
        elif available_keywords:
            distractors.extend(random.sample(available_keywords, min(2, len(available_keywords))))
        
        # Strategy 2: Domain-specific alternatives (EXPANDED)
        domain_alternatives = {
            # Linux/Unix commands
            'cat': ['tac', 'more', 'less', 'head', 'tail', 'nl'],
            'ls': ['dir', 'find', 'locate', 'tree', 'pwd'],
            'echo': ['printf', 'print', 'cat', 'tee'],
            'grep': ['egrep', 'fgrep', 'awk', 'sed', 'find'],
            'sed': ['awk', 'tr', 'cut', 'grep', 'perl'],
            'chmod': ['chown', 'chgrp', 'umask', 'setfacl', 'chattr'],
            'mkdir': ['rmdir', 'touch', 'mktemp', 'install', 'mkfifo'],
            'cp': ['mv', 'rsync', 'scp', 'dd', 'install'],
            'rm': ['rmdir', 'unlink', 'shred', 'del', 'erase'],
            'tar': ['gzip', 'zip', 'bzip2', 'xz', 'compress'],
            
            # Programming concepts
            'variable': ['constant', 'parameter', 'argument', 'attribute', 'property'],
            'function': ['method', 'procedure', 'routine', 'subroutine', 'module'],
            'loop': ['iteration', 'recursion', 'cycle', 'traverse', 'repeat'],
            'array': ['list', 'vector', 'matrix', 'tuple', 'collection'],
            'class': ['object', 'structure', 'interface', 'module', 'namespace'],
            
            # Network terms
            'router': ['switch', 'gateway', 'bridge', 'hub', 'modem'],
            'protocol': ['standard', 'convention', 'interface', 'specification', 'format'],
            'packet': ['frame', 'datagram', 'segment', 'message', 'block'],
            
            # Database terms
            'table': ['view', 'relation', 'entity', 'schema', 'index'],
            'query': ['statement', 'command', 'request', 'expression', 'clause'],
            'index': ['key', 'constraint', 'trigger', 'view', 'cursor']
        }
        
        if correct_answer.lower() in domain_alternatives:
            alternatives = domain_alternatives[correct_answer.lower()]
            distractors.extend(random.sample(alternatives, min(2, len(alternatives))))
        
        # Strategy 3: IMPROVED - Generate semantic variations
        if len(distractors) < 3:
            semantic_variations = self._generate_semantic_variations(correct_answer, context_type)
            distractors.extend(semantic_variations[:3 - len(distractors)])
        
        # Strategy 4: IMPROVED - Pattern-based generation
        if len(distractors) < 3:
            pattern_distractors = self._generate_pattern_based_distractors(correct_answer)
            distractors.extend(pattern_distractors[:3 - len(distractors)])
        
        # Remove duplicates and correct answer
        distractors = [d for d in distractors if d.lower() != correct_answer.lower()]
        distractors = list(dict.fromkeys(distractors))  # Remove duplicates while preserving order
        
        # Final validation: ensure distractors are plausible
        validated_distractors = []
        for d in distractors:
            if len(d) >= 2 and not self._contains_forbidden_words(d):
                validated_distractors.append(d)
        
        return validated_distractors
    
    def _generate_semantic_variations(self, keyword, context_type):
        """
        IMPROVED: Generate semantic variations of the keyword.
        """
        variations = []
        
        # Prefix/suffix variations
        prefixes = ['pre', 'post', 'sub', 'super', 'meta', 'hyper']
        suffixes = ['er', 'or', 'ing', 'ed', 'ion', 'tion']
        
        # Add prefix variations
        for prefix in prefixes:
            variations.append(f"{prefix}{keyword}")
        
        # Add suffix variations (simple)
        for suffix in suffixes:
            if not keyword.endswith(suffix):
                variations.append(f"{keyword}{suffix}")
        
        # Context-based variations
        if context_type == 'command':
            variations.extend([f"{keyword}_{v}" for v in ['cmd', 'util', 'tool']])
        elif context_type == 'function':
            variations.extend([f"{keyword}_{v}" for v in ['func', 'method', 'call']])
        elif context_type == 'data':
            variations.extend([f"{keyword}_{v}" for v in ['data', 'info', 'value']])
        
        return variations[:5]  # Return top 5
    
    def _generate_pattern_based_distractors(self, keyword):
        """
        IMPROVED: Generate pattern-based distractors.
        """
        distractors = []
        
        # Similar length words
        if len(keyword) >= 4:
            # Generate abbreviation-style distractors
            if keyword.isupper():
                # For acronyms like CPU, RAM
                alternatives = ['GPU', 'TPU', 'ALU', 'FPU', 'MMU', 'DSP']
                distractors.extend([a for a in alternatives if a != keyword])
            else:
                # For regular words, create variations
                chars = list(keyword)
                if len(chars) >= 3:
                    # Swap adjacent characters
                    chars[0], chars[1] = chars[1], chars[0]
                    distractors.append(''.join(chars))
                    
                    # Reverse string
                    distractors.append(keyword[::-1])
        
        return distractors[:3]
    
    def _polish_question_text(self, text):
        """IMPROVED: Polish question text for natural flow."""
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Fix punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        
        # Ensure proper capitalization
        if text:
            text = text[0].upper() + text[1:]
        
        # Ensure proper ending
        if text and not text.endswith(('?', '.', '!')):
            # Add question mark for interrogative sentences
            if any(text.lower().startswith(q) for q in ['what', 'which', 'how', 'when', 'where', 'who', 'why']):
                text += '?'
            else:
                text += '.'
        
        # Remove redundant words
        text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
        
        return text
    
    def _apply_natural_rephrasing(self, text):
        """
        NEW: Apply natural rephrasing to make questions sound more human and less AI-generated.
        """
        if not text or not hasattr(self, 'natural_rephrasing'):
            return text
        
        # Randomly apply rephrasing (70% chance)
        if random.random() > 0.7:
            return text
        
        # Apply rephrasing transformations
        for formal_phrase, casual_options in self.natural_rephrasing.items():
            if formal_phrase in text.lower():
                # Replace with a random casual alternative
                casual_replacement = random.choice(casual_options)
                
                # Preserve case of first letter
                if text.lower().find(formal_phrase) == 0:
                    casual_replacement = casual_replacement.capitalize()
                
                # Case-insensitive replacement
                pattern = re.compile(re.escape(formal_phrase), re.IGNORECASE)
                text = pattern.sub(casual_replacement, text, count=1)
                break  # Only rephrase one thing per question
        
        return text
    
    def _add_conversation_starter(self, text):
        """
        NEW: Occasionally add a natural conversation starter to questions.
        """
        if not hasattr(self, 'conversation_starters'):
            return text
        
        # 30% chance to add a starter
        if random.random() < 0.3:
            starter = random.choice(self.conversation_starters)
            if starter and not text.startswith(starter):
                # Adjust capitalization
                if starter.strip():  # If not empty
                    text = text[0].lower() + text[1:] if len(text) > 1 else text.lower()
                return starter + text
        
        return text
    
    
    def generate_questions(self, text, question_types=None, num_questions=10):
        """
        IMPROVED: Generate humanized questions from text with better quality control.
        """
        if question_types is None:
            question_types = ['multiple_choice']
        
        # Extract keywords using TF-IDF
        self.tfidf_engine.add_document(text)
        keywords = self.tfidf_engine.extract_keywords(text, top_n=num_questions * 10)
        
        logger.info(f"Extracted {len(keywords)} keywords for question generation")
        
        # Abstract keywords in text
        from app.module_processor.content_extractor import ContentExtractor
        extractor = ContentExtractor()
        abstracted_data = extractor._abstract_keywords(text, keywords)
        abstracted_text = abstracted_data[0]
        keyword_map = abstracted_data[1]
        
        questions = []
        attempts = 0
        max_attempts = num_questions * 20  # IMPROVED: More attempts for better quality
        
        # IMPROVED: Prioritize high-value keywords
        keywords.sort(key=lambda x: x[1], reverse=True)
        
        while len(questions) < num_questions and attempts < max_attempts:
            attempts += 1
            
            # Select unused keyword
            available_keywords = [k for k, _ in keywords if k not in self.used_keywords]
            if not available_keywords:
                logger.warning("No more available keywords")
                break
            
            # IMPROVED: Select from top keywords with some randomness
            top_n = min(20, len(available_keywords))
            keyword = random.choice(available_keywords[:top_n])
            self.used_keywords.add(keyword)
            
            # Select parameters with better distribution
            bloom_level = random.choice(['remembering', 'understanding', 'applying', 'analyzing', 'evaluating'])
            difficulty = random.choice(['easy', 'medium', 'hard'])
            points = {'easy': 1, 'medium': 2, 'hard': random.randint(3, 5)}[difficulty]
            
            # Extract relevant context
            context = self._extract_context_for_keyword(abstracted_text, keyword)
            
            # Generate humanized MCQ
            question = self.generate_humanized_mcq(
                context, keyword, keyword_map, bloom_level, difficulty, points
            )
            
            if question:
                q_key = question['question'].lower()
                if q_key not in self.generated_questions:
                    questions.append(question)
                    self.generated_questions.add(q_key)
                    logger.info(f"Generated humanized question #{len(questions)}")
            
            # IMPROVED: Log progress every 10 attempts
            if attempts % 10 == 0:
                logger.info(f"Progress: {len(questions)}/{num_questions} questions, {attempts} attempts")
        
        logger.info(f"Generated {len(questions)} humanized MCQs in {attempts} attempts")
        return questions
    
    def _extract_context_for_keyword(self, text, keyword):
        """IMPROVED: Extract relevant context for a keyword."""
        sentences = sent_tokenize(text) if text.strip() else []
        
        # Look for sentences containing the keyword or its placeholder
        keyword_sentences = [
            s.strip() for s in sentences 
            if keyword.lower() in s.lower() or f'<concept:{keyword}>' in s
        ]
        
        if keyword_sentences:
            # IMPROVED: Select sentence with most context
            best_sentence = max(keyword_sentences, key=len)
            return best_sentence
        
        # Fallback: return beginning of text
        return text[:500] if text else None
    
    def humanize_question_for_teacher_authenticity(self, question_data):
        """
        IMPROVED: Final polish ensuring teacher authenticity with additional checks.
        """
        try:
            if not question_data or 'question' not in question_data:
                return question_data
            
            q_text = question_data['question']
            
            # Polish - multiple passes for better humanization
            q_text = self._polish_question_text(q_text)
            
            # NEW: Apply natural rephrasing to sound less formal
            q_text = self._apply_natural_rephrasing(q_text)
            
            # NEW: Occasionally add conversational starter
            q_text = self._add_conversation_starter(q_text)
            
            # Final polish after modifications
            q_text = self._polish_question_text(q_text)
            
            # IMPROVED: Additional validation checks
            if len(q_text) < 15:
                logger.error(f"Question too short: {q_text}")
                return None
            
            if len(q_text) > 200:
                logger.warning(f"Question too long, truncating: {q_text[:50]}...")
                q_text = q_text[:197] + "..."
            
            # Final validation
            if self._contains_forbidden_words(q_text):
                logger.error(f"Failed humanization - forbidden words remain: {q_text}")
                return None
            
            # Validate options if MCQ
            if question_data.get('question_type') == 'multiple_choice':
                options = question_data.get('options', [])
                if len(options) != 4:
                    logger.error(f"Invalid number of options: {len(options)}")
                    return None
                
                # Ensure answer is in options
                answer = question_data.get('answer')
                if answer not in options:
                    logger.error(f"Answer not in options: {answer}")
                    return None
            
            question_data['question'] = q_text
            return question_data
            
        except Exception as e:
            logger.error(f"Error humanizing question: {str(e)}")
            return question_data