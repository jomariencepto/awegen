import json
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TOSGenerator:
    def __init__(self):
        self.cognitive_levels = ['remembering', 'understanding', 'applying', 'analyzing', 'evaluating', 'creating']
        self.difficulty_levels = ['easy', 'medium', 'hard']
    
    def generate_tos(self, questions, topics, exam_config):
        """Generate Table of Specification (TOS) with complete breakdown"""
        # Initialize TOS structure
        tos = {
            'exam_title': exam_config.get('title', 'Untitled Exam'),
            'total_questions': len(questions),
            'duration_minutes': exam_config.get('duration_minutes', 60),
            'topics': topics,
            'cognitive_distribution': {},
            'difficulty_distribution': {},
            'question_type_distribution': {},
            'points_distribution': {},
            'topic_cognitive_matrix': {},
            'topic_difficulty_matrix': {},
            'cognitive_difficulty_matrix': {}
        }
        
        # Initialize matrices
        for topic in topics:
            tos['topic_cognitive_matrix'][topic] = {level: 0 for level in self.cognitive_levels}
            tos['topic_difficulty_matrix'][topic] = {level: 0 for level in self.difficulty_levels}
        
        # Initialize cognitive-difficulty matrix
        for cognitive_level in self.cognitive_levels:
            tos['cognitive_difficulty_matrix'][cognitive_level] = {level: 0 for level in self.difficulty_levels}
        
        # Track total points
        total_points = 0
        points_by_difficulty = {'easy': 0, 'medium': 0, 'hard': 0}
        points_by_cognitive = {level: 0 for level in self.cognitive_levels}
        points_by_question_type = {}
        
        # Process questions
        for question in questions:
            topic = question.get('topic', 'General')
            cognitive_level = question.get('bloom_level', 'remembering')
            difficulty = question.get('difficulty_level', 'medium')
            question_type = question.get('question_type', 'multiple_choice')
            points = question.get('points', 1)
            
            # Update total points
            total_points += points
            
            # Update cognitive distribution
            if cognitive_level in tos['cognitive_distribution']:
                tos['cognitive_distribution'][cognitive_level] += 1
            else:
                tos['cognitive_distribution'][cognitive_level] = 1
            
            # Update difficulty distribution
            if difficulty in tos['difficulty_distribution']:
                tos['difficulty_distribution'][difficulty] += 1
            else:
                tos['difficulty_distribution'][difficulty] = 1
            
            # Update question type distribution
            if question_type in tos['question_type_distribution']:
                tos['question_type_distribution'][question_type] += 1
            else:
                tos['question_type_distribution'][question_type] = 1
            
            # Update points by difficulty
            if difficulty in points_by_difficulty:
                points_by_difficulty[difficulty] += points
            
            # Update points by cognitive level
            if cognitive_level in points_by_cognitive:
                points_by_cognitive[cognitive_level] += points
            
            # Update points by question type
            if question_type in points_by_question_type:
                points_by_question_type[question_type] += points
            else:
                points_by_question_type[question_type] = points
            
            # Update topic-cognitive matrix
            if topic in tos['topic_cognitive_matrix'] and cognitive_level in tos['topic_cognitive_matrix'][topic]:
                tos['topic_cognitive_matrix'][topic][cognitive_level] += 1
            
            # Update topic-difficulty matrix
            if topic in tos['topic_difficulty_matrix'] and difficulty in tos['topic_difficulty_matrix'][topic]:
                tos['topic_difficulty_matrix'][topic][difficulty] += 1
            
            # Update cognitive-difficulty matrix
            if cognitive_level in tos['cognitive_difficulty_matrix'] and difficulty in tos['cognitive_difficulty_matrix'][cognitive_level]:
                tos['cognitive_difficulty_matrix'][cognitive_level][difficulty] += 1
        
        # Store points information
        tos['total_points'] = total_points
        tos['points_by_difficulty'] = points_by_difficulty
        tos['points_by_cognitive'] = points_by_cognitive
        tos['points_by_question_type'] = points_by_question_type
        
        # Calculate percentages
        tos['cognitive_percentages'] = self._calculate_percentages(tos['cognitive_distribution'], len(questions))
        tos['difficulty_percentages'] = self._calculate_percentages(tos['difficulty_distribution'], len(questions))
        tos['question_type_percentages'] = self._calculate_percentages(tos['question_type_distribution'], len(questions))
        
        # Calculate points percentages
        tos['points_percentages_by_difficulty'] = self._calculate_percentages(points_by_difficulty, total_points)
        tos['points_percentages_by_cognitive'] = self._calculate_percentages(points_by_cognitive, total_points)
        tos['points_percentages_by_question_type'] = self._calculate_percentages(points_by_question_type, total_points)
        
        # Generate summary statistics
        tos['summary'] = self._generate_summary(tos, questions)
        
        return tos
    
    def _calculate_percentages(self, distribution, total):
        """Calculate percentages for distribution"""
        percentages = {}
        for key, count in distribution.items():
            percentages[key] = round((count / total) * 100, 2) if total > 0 else 0
        return percentages
    
    def _generate_summary(self, tos, questions):
        """Generate summary statistics for TOS"""
        summary = {
            'total_questions': len(questions),
            'total_points': tos['total_points'],
            'average_points_per_question': round(tos['total_points'] / len(questions), 2) if questions else 0,
            'question_types_count': len(tos['question_type_distribution']),
            'topics_covered': len(tos['topics']),
            'cognitive_levels_used': len([k for k, v in tos['cognitive_distribution'].items() if v > 0]),
            'difficulty_breakdown': {
                'easy': {
                    'count': tos['difficulty_distribution'].get('easy', 0),
                    'percentage': tos['difficulty_percentages'].get('easy', 0),
                    'points': tos['points_by_difficulty'].get('easy', 0),
                    'points_percentage': tos['points_percentages_by_difficulty'].get('easy', 0)
                },
                'medium': {
                    'count': tos['difficulty_distribution'].get('medium', 0),
                    'percentage': tos['difficulty_percentages'].get('medium', 0),
                    'points': tos['points_by_difficulty'].get('medium', 0),
                    'points_percentage': tos['points_percentages_by_difficulty'].get('medium', 0)
                },
                'hard': {
                    'count': tos['difficulty_distribution'].get('hard', 0),
                    'percentage': tos['difficulty_percentages'].get('hard', 0),
                    'points': tos['points_by_difficulty'].get('hard', 0),
                    'points_percentage': tos['points_percentages_by_difficulty'].get('hard', 0)
                }
            },
            'cognitive_breakdown': {}
        }
        
        # Add cognitive breakdown
        for level in self.cognitive_levels:
            if level in tos['cognitive_distribution']:
                summary['cognitive_breakdown'][level] = {
                    'count': tos['cognitive_distribution'][level],
                    'percentage': tos['cognitive_percentages'][level],
                    'points': tos['points_by_cognitive'].get(level, 0),
                    'points_percentage': tos['points_percentages_by_cognitive'].get(level, 0)
                }
        
        return summary
    
    def generate_tos_from_config(self, exam_config, module_content):
        """Generate TOS based on exam configuration and module content"""
        # Extract topics from module content
        topics = list(set([item.get('topic', 'General') for item in module_content]))
        
        # Generate question distribution based on config
        question_distribution = exam_config.get('question_distribution', {})
        
        # Create empty TOS structure
        tos = {
            'exam_title': exam_config.get('title', 'Untitled Exam'),
            'total_questions': sum(question_distribution.values()),
            'duration_minutes': exam_config.get('duration_minutes', 60),
            'topics': topics,
            'cognitive_distribution': {},
            'difficulty_distribution': {},
            'topic_cognitive_matrix': {},
            'topic_difficulty_matrix': {}
        }
        
        # Initialize matrices
        for topic in topics:
            tos['topic_cognitive_matrix'][topic] = {level: 0 for level in self.cognitive_levels}
            tos['topic_difficulty_matrix'][topic] = {level: 0 for level in self.difficulty_levels}
        
        # Fill TOS based on distribution
        for cognitive_level, count in question_distribution.items():
            tos['cognitive_distribution'][cognitive_level] = count
            
            # Distribute questions across topics (simple equal distribution)
            questions_per_topic = max(1, count // len(topics))
            remaining = count % len(topics)
            
            for i, topic in enumerate(topics):
                topic_count = questions_per_topic + (1 if i < remaining else 0)
                tos['topic_cognitive_matrix'][topic][cognitive_level] = topic_count
                
                # Distribute difficulties (simple equal distribution)
                easy_count = topic_count // 3
                medium_count = topic_count // 3
                hard_count = topic_count - easy_count - medium_count
                
                tos['topic_difficulty_matrix'][topic]['easy'] = easy_count
                tos['topic_difficulty_matrix'][topic]['medium'] = medium_count
                tos['topic_difficulty_matrix'][topic]['hard'] = hard_count
        
        # Calculate difficulty distribution
        for topic in topics:
            for difficulty in self.difficulty_levels:
                count = tos['topic_difficulty_matrix'][topic][difficulty]
                if difficulty in tos['difficulty_distribution']:
                    tos['difficulty_distribution'][difficulty] += count
                else:
                    tos['difficulty_distribution'][difficulty] = count
        
        # Calculate percentages
        tos['cognitive_percentages'] = self._calculate_percentages(tos['cognitive_distribution'], tos['total_questions'])
        tos['difficulty_percentages'] = self._calculate_percentages(tos['difficulty_distribution'], tos['total_questions'])
        
        return tos
    
    def validate_tos(self, tos):
        """Validate TOS structure and content"""
        errors = []
        
        # Check required fields
        required_fields = ['exam_title', 'total_questions', 'topics', 'cognitive_distribution', 'difficulty_distribution']
        for field in required_fields:
            if field not in tos:
                errors.append(f"Missing required field: {field}")
        
        # Check if total questions match distribution
        total_from_cognitive = sum(tos.get('cognitive_distribution', {}).values())
        total_from_difficulty = sum(tos.get('difficulty_distribution', {}).values())
        
        if total_from_cognitive != tos.get('total_questions', 0):
            errors.append(f"Cognitive distribution sum ({total_from_cognitive}) doesn't match total questions ({tos.get('total_questions', 0)})")
        
        if total_from_difficulty != tos.get('total_questions', 0):
            errors.append(f"Difficulty distribution sum ({total_from_difficulty}) doesn't match total questions ({tos.get('total_questions', 0)})")
        
        # Check if all topics are covered
        topics = tos.get('topics', [])
        for topic in topics:
            if topic not in tos.get('topic_cognitive_matrix', {}):
                errors.append(f"Topic '{topic}' missing from cognitive matrix")
            
            if topic not in tos.get('topic_difficulty_matrix', {}):
                errors.append(f"Topic '{topic}' missing from difficulty matrix")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }
    
    def export_tos_to_json(self, tos, file_path):
        """Export TOS to JSON file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(tos, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error exporting TOS to JSON: {str(e)}")
            return False
    
    def import_tos_from_json(self, file_path):
        """Import TOS from JSON file"""
        try:
            with open(file_path, 'r') as f:
                tos = json.load(f)
            
            # Validate imported TOS
            validation = self.validate_tos(tos)
            if not validation['is_valid']:
                logger.error(f"Invalid TOS structure: {validation['errors']}")
                return None
            
            return tos
        except Exception as e:
            logger.error(f"Error importing TOS from JSON: {str(e)}")
            return None