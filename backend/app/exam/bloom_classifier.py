import random
import re
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BloomClassifier:
    """
    IMPROVED: Classifies questions according to Bloom's Taxonomy with:
    - Enhanced keyword matching
    - Better pattern recognition
    - Context-aware classification
    - Confidence scoring
    """
    
    def __init__(self):
        # IMPROVED: Enhanced keywords and patterns for each Bloom's level
        self.bloom_levels = {
            'remembering': {
                'keywords': [
                    'define', 'list', 'identify', 'name', 'recall', 'recognize',
                    'state', 'describe', 'label', 'match', 'select', 'memorize',
                    'who', 'what', 'when', 'where', 'spell', 'tell', 'show',
                    'locate', 'find', 'choose', 'recite', 'repeat', 'arrange'
                ],
                'patterns': [
                    r'\bwhat is\b',
                    r'\bwho is\b',
                    r'\bwho was\b',
                    r'\bwhen did\b',
                    r'\bwhere is\b',
                    r'\blist\b',
                    r'\bname\b',
                    r'\bdefine\b',
                    r'\bidentify the\b',
                    r'\brecall\b',
                    r'\bstate the\b',
                    r'\bwhich of the following\b'
                ],
                'weight': 1
            },
            'understanding': {
                'keywords': [
                    'explain', 'describe', 'interpret', 'summarize', 'paraphrase',
                    'infer', 'compare', 'contrast', 'classify', 'illustrate',
                    'discuss', 'distinguish', 'estimate', 'extend', 'predict',
                    'associate', 'differentiate', 'express', 'outline', 'review'
                ],
                'patterns': [
                    r'\bexplain\b',
                    r'\bdescribe how\b',
                    r'\bwhat does .+ mean\b',
                    r'\bsummarize\b',
                    r'\bcompare .+ and\b',
                    r'\bcontrast .+ and\b',
                    r'\bhow would you\b',
                    r'\bwhat is the difference between\b',
                    r'\binterpret\b',
                    r'\billustrate\b',
                    r'\bdistinguish between\b'
                ],
                'weight': 2
            },
            'applying': {
                'keywords': [
                    'apply', 'use', 'implement', 'demonstrate', 'execute',
                    'carry out', 'employ', 'utilize', 'practice', 'show',
                    'solve', 'modify', 'operate', 'prepare', 'compute',
                    'calculate', 'construct', 'manipulate', 'relate', 'simulate'
                ],
                'patterns': [
                    r'\bhow would you use\b',
                    r'\bapply .+ to\b',
                    r'\buse .+ to\b',
                    r'\bdemonstrate how\b',
                    r'\bshow how\b',
                    r'\bsolve\b',
                    r'\bimplement\b',
                    r'\bcalculate\b',
                    r'\bcompute\b',
                    r'\bgiven .+, what\b',
                    r'\bin what way\b'
                ],
                'weight': 2
            },
            'analyzing': {
                'keywords': [
                    'analyze', 'examine', 'investigate', 'categorize', 'differentiate',
                    'distinguish', 'break down', 'organize', 'deconstruct',
                    'relate', 'separate', 'order', 'dissect', 'inspect',
                    'survey', 'detect', 'diagnose', 'divide', 'explore'
                ],
                'patterns': [
                    r'\banalyze\b',
                    r'\bexamine\b',
                    r'\bwhat are the parts of\b',
                    r'\bhow does .+ work\b',
                    r'\bwhat is the relationship between\b',
                    r'\bwhy does\b',
                    r'\bcompare and contrast\b',
                    r'\bcategorize\b',
                    r'\bbreak down\b',
                    r'\binvestigate\b',
                    r'\bwhat factors\b'
                ],
                'weight': 3
            },
            'evaluating': {
                'keywords': [
                    'evaluate', 'judge', 'critique', 'assess', 'justify',
                    'defend', 'argue', 'recommend', 'validate', 'rate',
                    'prioritize', 'decide', 'choose', 'appraise', 'conclude',
                    'criticize', 'defend', 'support', 'test', 'verify'
                ],
                'patterns': [
                    r'\bevaluate\b',
                    r'\bjudge\b',
                    r'\bwhat is your opinion\b',
                    r'\bdo you agree\b',
                    r'\bis .+ effective\b',
                    r'\bshould\b',
                    r'\bwould you recommend\b',
                    r'\bassess\b',
                    r'\bcritique\b',
                    r'\bjustify\b',
                    r'\bwhich is better\b',
                    r'\bwhat is the best\b'
                ],
                'weight': 3
            },
            'creating': {
                'keywords': [
                    'create', 'design', 'develop', 'construct', 'produce',
                    'formulate', 'plan', 'build', 'invent', 'compose',
                    'generate', 'hypothesize', 'devise', 'originate',
                    'synthesize', 'assemble', 'compile', 'integrate', 'propose'
                ],
                'patterns': [
                    r'\bcreate\b',
                    r'\bdesign\b',
                    r'\bdevelop\b',
                    r'\bwhat would you do\b',
                    r'\bhow would you create\b',
                    r'\bpropose\b',
                    r'\bformulate\b',
                    r'\bsynthesize\b',
                    r'\bconstruct a\b',
                    r'\bdevise\b',
                    r'\bgenerate\b'
                ],
                'weight': 4
            }
        }
    
    def classify_question(self, question_text):
        """
        IMPROVED: Classify a single question with confidence scoring.
        
        Args:
            question_text (str): The question text to classify
            
        Returns:
            str: The Bloom's level (remembering, understanding, applying, etc.)
        """
        if not question_text or not isinstance(question_text, str):
            return 'remembering'
        
        question_lower = question_text.lower()
        scores = {}
        
        # Calculate scores for each level
        for level, data in self.bloom_levels.items():
            score = 0
            weight = data.get('weight', 1)
            
            # Check for keyword matches
            for keyword in data['keywords']:
                if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):
                    score += weight
            
            # Check for pattern matches (higher weight)
            for pattern in data['patterns']:
                if re.search(pattern, question_lower):
                    score += weight * 2
            
            scores[level] = score
        
        # Return the level with highest score
        max_score = max(scores.values())
        
        if max_score == 0:
            # IMPROVED: Fallback classification based on question structure
            return self._fallback_classification(question_text)
        
        return max(scores, key=scores.get)
    
    def _fallback_classification(self, question_text):
        """
        IMPROVED: Fallback classification based on question structure.
        """
        question_lower = question_text.lower()
        
        # Check for question words
        if any(word in question_lower for word in ['what is', 'who is', 'when', 'where']):
            return 'remembering'
        
        # Check for explanation/description
        if any(word in question_lower for word in ['explain', 'describe', 'how', 'why']):
            return 'understanding'
        
        # Check for application
        if any(word in question_lower for word in ['use', 'apply', 'solve', 'demonstrate']):
            return 'applying'
        
        # Check for analysis
        if any(word in question_lower for word in ['analyze', 'compare', 'examine']):
            return 'analyzing'
        
        # Check for evaluation
        if any(word in question_lower for word in ['should', 'better', 'best', 'recommend']):
            return 'evaluating'
        
        # Check for creation
        if any(word in question_lower for word in ['create', 'design', 'develop', 'propose']):
            return 'creating'
        
        # Default
        return 'remembering'
    
    def classify_with_confidence(self, question_text):
        """
        NEW: Classify question and return confidence score.
        
        Returns:
            tuple: (level, confidence_score)
        """
        if not question_text or not isinstance(question_text, str):
            return ('remembering', 0.5)
        
        question_lower = question_text.lower()
        scores = {}
        
        for level, data in self.bloom_levels.items():
            score = 0
            weight = data.get('weight', 1)
            
            # Keyword matches
            for keyword in data['keywords']:
                if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):
                    score += weight
            
            # Pattern matches
            for pattern in data['patterns']:
                if re.search(pattern, question_lower):
                    score += weight * 2
            
            scores[level] = score
        
        # Get max score and level
        max_score = max(scores.values())
        
        if max_score == 0:
            return (self._fallback_classification(question_text), 0.5)
        
        classified_level = max(scores, key=scores.get)
        
        # Calculate confidence
        total_score = sum(scores.values())
        confidence = max_score / total_score if total_score > 0 else 0.5
        
        return (classified_level, confidence)
    
    def classify_questions(self, questions):
        """
        IMPROVED: Classify multiple questions and add bloom_level to each.
        """
        for question in questions:
            if 'bloom_level' not in question or not question.get('bloom_level'):
                question['bloom_level'] = self.classify_question(
                    question.get('question_text', '')
                )
        
        return questions
    
    def get_distribution(self, questions):
        """Get the distribution of questions across Bloom's levels."""
        distribution = {level: 0 for level in self.bloom_levels.keys()}
        
        for question in questions:
            bloom_level = question.get('bloom_level', 'remembering')
            if bloom_level in distribution:
                distribution[bloom_level] += 1
        
        return distribution
    
    def balance_questions(self, questions, target_distribution=None):
        """
        IMPROVED: Balance questions with better fallback strategy.
        """
        if target_distribution is None:
            target_distribution = {
                'remembering': 0.20,
                'understanding': 0.25,
                'applying': 0.25,
                'analyzing': 0.15,
                'evaluating': 0.10,
                'creating': 0.05
            }
        
        # Classify questions
        classified_questions = self.classify_questions(questions)
        
        # Group by Bloom level
        questions_by_level = {level: [] for level in self.bloom_levels.keys()}
        for question in classified_questions:
            level = question.get('bloom_level', 'remembering')
            questions_by_level[level].append(question)
        
        # Calculate target counts
        total_questions = len(questions)
        target_counts = {
            level: max(1, int(total_questions * ratio))
            for level, ratio in target_distribution.items()
        }
        
        # Adjust to match total exactly
        current_total = sum(target_counts.values())
        diff = total_questions - current_total
        
        if diff != 0:
            # Distribute difference across levels
            levels = list(target_counts.keys())
            for i in range(abs(diff)):
                if diff > 0:
                    level = min(levels, key=lambda l: target_counts[l])
                    target_counts[level] += 1
                else:
                    level = max(levels, key=lambda l: target_counts[l])
                    if target_counts[level] > 1:
                        target_counts[level] -= 1
        
        # Select questions to match distribution
        balanced_questions = []
        
        for level, count in target_counts.items():
            available = questions_by_level[level]
            
            if len(available) >= count:
                # IMPROVED: Prioritize higher quality questions
                # Sort by quality indicators
                available_sorted = sorted(
                    available,
                    key=lambda q: (
                        len(q.get('question_text', '').split()),  # Prefer longer questions
                        q.get('points', 1)  # Prefer higher point questions
                    ),
                    reverse=True
                )
                selected = available_sorted[:count]
                balanced_questions.extend(selected)
            else:
                # Take all available
                balanced_questions.extend(available)
                
                # Fill remaining from similar levels
                remaining = count - len(available)
                if remaining > 0:
                    priority_levels = self._get_level_priority(level)
                    
                    for other_level in priority_levels:
                        if remaining <= 0:
                            break
                        
                        other_available = [
                            q for q in questions_by_level[other_level]
                            if q not in balanced_questions
                        ]
                        
                        take = min(remaining, len(other_available))
                        if take > 0:
                            # Sort and select best
                            other_available_sorted = sorted(
                                other_available,
                                key=lambda q: len(q.get('question_text', '').split()),
                                reverse=True
                            )
                            selected = other_available_sorted[:take]
                            balanced_questions.extend(selected)
                            remaining -= take
        
        # Update question IDs
        for i, question in enumerate(balanced_questions):
            question['question_id'] = i + 1
        
        logger.info(f"Balanced questions: {self.get_distribution(balanced_questions)}")
        
        return balanced_questions
    
    def _get_level_priority(self, level):
        """
        IMPROVED: Get priority list based on cognitive proximity.
        """
        # Define cognitive proximity
        priorities = {
            'remembering': ['understanding', 'applying', 'analyzing', 'evaluating', 'creating'],
            'understanding': ['remembering', 'applying', 'analyzing', 'evaluating', 'creating'],
            'applying': ['understanding', 'analyzing', 'remembering', 'evaluating', 'creating'],
            'analyzing': ['applying', 'evaluating', 'understanding', 'creating', 'remembering'],
            'evaluating': ['analyzing', 'creating', 'applying', 'understanding', 'remembering'],
            'creating': ['evaluating', 'analyzing', 'applying', 'understanding', 'remembering']
        }
        
        return priorities.get(level, list(self.bloom_levels.keys()))
    
    def validate_distribution(self, questions, target_distribution):
        """
        NEW: Validate if questions match target distribution.
        
        Returns:
            dict: Validation results with metrics
        """
        current_distribution = self.get_distribution(questions)
        total = len(questions)
        
        validation = {
            'valid': True,
            'deviations': {},
            'total_questions': total
        }
        
        for level, target_ratio in target_distribution.items():
            target_count = int(total * target_ratio)
            current_count = current_distribution.get(level, 0)
            deviation = abs(current_count - target_count)
            
            validation['deviations'][level] = {
                'target': target_count,
                'current': current_count,
                'deviation': deviation,
                'acceptable': deviation <= max(1, total * 0.05)  # 5% tolerance
            }
            
            if not validation['deviations'][level]['acceptable']:
                validation['valid'] = False
        
        return validation