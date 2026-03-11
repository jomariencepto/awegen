import random
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QuestionRandomizer:
    def __init__(self):
        # Define the order of question types
        self.question_type_order = ['multiple_choice', 'true_false', 'fill_in_blank', 'identification', 'problem_solving']
    
    def group_by_question_type(self, questions):
        """Group questions by question type in a specific order"""
        try:
            # Group questions by type
            grouped_questions = {}
            for question in questions:
                q_type = question.get('question_type', 'multiple_choice')
                if q_type not in grouped_questions:
                    grouped_questions[q_type] = []
                grouped_questions[q_type].append(question)
            
            # Create ordered list based on predefined type order
            ordered_questions = []
            for q_type in self.question_type_order:
                if q_type in grouped_questions:
                    # Update question IDs within each type group
                    for i, question in enumerate(grouped_questions[q_type]):
                        question['question_id'] = len(ordered_questions) + i + 1
                    ordered_questions.extend(grouped_questions[q_type])
            
            return ordered_questions
            
        except Exception as e:
            logger.error(f"Error grouping questions by type: {str(e)}")
            return questions
    
    def randomize_questions(self, questions):
        """Randomize the order of questions"""
        try:
            # Create a copy of the questions list
            randomized = questions.copy()
            
            # Shuffle the questions
            random.shuffle(randomized)
            
            # Update question IDs to reflect new order
            for i, question in enumerate(randomized):
                question['question_id'] = i + 1
            
            return randomized
            
        except Exception as e:
            logger.error(f"Error randomizing questions: {str(e)}")
            return questions
    
    def randomize_options(self, questions):
        """Randomize the order of options for multiple-choice questions"""
        try:
            for question in questions:
                if question['question_type'] == 'multiple_choice' and 'options' in question:
                    # Get the correct answer
                    correct_answer = question['correct_answer']
                    
                    # Shuffle options
                    options = question['options'].copy()
                    random.shuffle(options)
                    
                    # Update options and find new position of correct answer
                    question['options'] = options
                    question['correct_answer'] = correct_answer  # Keep the correct answer text
            
            return questions
            
        except Exception as e:
            logger.error(f"Error randomizing options: {str(e)}")
            return questions
    
    def randomize_by_topic(self, questions, topics=None):
        """Randomize questions while ensuring topic distribution"""
        try:
            if topics is None:
                # Extract topics from questions
                topics = list(set([q.get('topic', 'General') for q in questions]))
            
            # Group questions by topic
            questions_by_topic = {}
            for question in questions:
                topic = question.get('topic', 'General')
                if topic not in questions_by_topic:
                    questions_by_topic[topic] = []
                questions_by_topic[topic].append(question)
            
            # Randomize questions within each topic
            randomized_questions = []
            for topic in topics:
                if topic in questions_by_topic:
                    topic_questions = questions_by_topic[topic]
                    random.shuffle(topic_questions)
                    randomized_questions.extend(topic_questions)
            
            # Update question IDs
            for i, question in enumerate(randomized_questions):
                question['question_id'] = i + 1
            
            return randomized_questions
            
        except Exception as e:
            logger.error(f"Error randomizing by topic: {str(e)}")
            return questions
    
    def randomize_by_difficulty(self, questions, difficulties=None):
        """Randomize questions while ensuring difficulty distribution"""
        try:
            if difficulties is None:
                difficulties = ['easy', 'medium', 'hard']
            
            # Group questions by difficulty
            questions_by_difficulty = {}
            for question in questions:
                difficulty = question.get('difficulty', 'medium')
                if difficulty not in questions_by_difficulty:
                    questions_by_difficulty[difficulty] = []
                questions_by_difficulty[difficulty].append(question)
            
            # Randomize questions within each difficulty level
            randomized_questions = []
            for difficulty in difficulties:
                if difficulty in questions_by_difficulty:
                    diff_questions = questions_by_difficulty[difficulty]
                    random.shuffle(diff_questions)
                    randomized_questions.extend(diff_questions)
            
            # Update question IDs
            for i, question in enumerate(randomized_questions):
                question['question_id'] = i + 1
            
            return randomized_questions
            
        except Exception as e:
            logger.error(f"Error randomizing by difficulty: {str(e)}")
            return questions
    
    def randomize_by_bloom_level(self, questions, bloom_levels=None):
        """Randomize questions while ensuring Bloom's level distribution"""
        try:
            if bloom_levels is None:
                bloom_levels = ['remembering', 'understanding', 'applying', 'analyzing', 'evaluating', 'creating']
            
            # Group questions by Bloom's level
            questions_by_bloom = {}
            for question in questions:
                bloom_level = question.get('bloom_level', 'remembering')
                if bloom_level not in questions_by_bloom:
                    questions_by_bloom[bloom_level] = []
                questions_by_bloom[bloom_level].append(question)
            
            # Randomize questions within each Bloom's level
            randomized_questions = []
            for bloom_level in bloom_levels:
                if bloom_level in questions_by_bloom:
                    bloom_questions = questions_by_bloom[bloom_level]
                    random.shuffle(bloom_questions)
                    randomized_questions.extend(bloom_questions)
            
            # Update question IDs
            for i, question in enumerate(randomized_questions):
                question['question_id'] = i + 1
            
            return randomized_questions
            
        except Exception as e:
            logger.error(f"Error randomizing by Bloom's level: {str(e)}")
            return questions