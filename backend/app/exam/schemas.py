from math import isclose
from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from app.exam.models import Exam, ExamQuestion, ExamCategory, ExamSubmission, ExamAnswer


class ExamCategorySchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ExamCategory
        load_instance = True


class ExamQuestionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ExamQuestion
        load_instance = True
        include_fk = True


class ExamSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Exam
        load_instance = True
        include_fk = True
    
    questions = fields.Nested(ExamQuestionSchema, many=True)


class ExamSubmissionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ExamSubmission
        load_instance = True
        include_fk = True


class ExamAnswerSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ExamAnswer
        load_instance = True
        include_fk = True


# Schema for module with teaching hours
class ModuleWithHoursSchema(Schema):
    module_id = fields.Int(required=True)
    teaching_hours = fields.Float(required=True, validate=validate.Range(min=0))


class ModuleQuestionTargetSchema(Schema):
    module_id = fields.Int(required=True)
    count = fields.Int(required=True, validate=validate.Range(min=0))


# NEW: Schema for difficulty distribution per question type
class DifficultyDistributionSchema(Schema):
    easy = fields.Int(missing=0)
    medium = fields.Int(missing=0)
    hard = fields.Int(missing=0)


# UPDATED: Schema for question type with points, count, difficulty distribution, and bloom level
class QuestionTypeWithDetailsSchema(Schema):
    type = fields.Str(required=True)
    count = fields.Int(required=True)  # Number of questions
    points = fields.Int(required=True)  # Points per question
    bloom_level = fields.Str(missing='random', allow_none=True)
    difficulty_distribution = fields.Nested(DifficultyDistributionSchema, required=True)
    description = fields.Str(missing="", allow_none=True)
    
    @validates_schema
    def validate_difficulty_total(self, data, **kwargs):
        """Ensure difficulty distribution matches count"""
        diff_dist = data.get('difficulty_distribution', {})
        total_diff = diff_dist.get('easy', 0) + diff_dist.get('medium', 0) + diff_dist.get('hard', 0)
        count = data.get('count', 0)
        
        if total_diff != count:
            raise ValidationError(
                f"Difficulty distribution ({total_diff}) must match question count ({count})"
            )


# UPDATED: Match frontend data structure with enhanced question type details
class ExamCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(missing="")
    category_id = fields.Int(required=True)
    start_time = fields.DateTime(allow_none=True, missing=None)
    end_time = fields.DateTime(allow_none=True, missing=None)
    duration_minutes = fields.Int(missing=60)
    num_questions = fields.Int(required=True)  # Total questions
    passing_score = fields.Int(missing=75)
    score_limit = fields.Int(missing=None, allow_none=True)
    allocated_minutes = fields.Int(missing=None, allow_none=True)
    
    # Support multiple modules with teaching hours
    modules = fields.List(fields.Nested(ModuleWithHoursSchema), required=True)
    total_hours = fields.Float(required=True, validate=validate.Range(min=0))
    module_coverage_mode = fields.Str(missing='hours', validate=validate.OneOf(['hours', 'percent']))
    module_question_targets = fields.List(
        fields.Nested(ModuleQuestionTargetSchema),
        missing=[]
    )
    
    # NEW: Detailed question types with difficulty control
    question_types_details = fields.List(
        fields.Nested(QuestionTypeWithDetailsSchema), 
        required=True
    )
    
    # Optional: Legacy support
    question_types = fields.List(fields.Str(), missing=[])
    question_types_with_points = fields.List(fields.Dict(), missing=[])
    
    # Optional fields
    cognitive_distribution = fields.Dict(missing={
        'remembering': 0.30,
        'understanding': 0.20,
        'applying': 0.20,
        'analyzing': 0.10,
        'evaluating': 0.10,
        'creating': 0.10
    })
    
    @validates_schema
    def validate_question_types(self, data, **kwargs):
        """Validate question types details"""
        question_types_details = data.get('question_types_details', [])
        
        if not question_types_details:
            raise ValidationError('At least one question type is required')
        
        # Validate total questions match
        total_count = sum(qt['count'] for qt in question_types_details)
        num_questions = data.get('num_questions', 0)
        
        if total_count != num_questions:
            raise ValidationError(
                f'Sum of question counts ({total_count}) must match total questions ({num_questions})'
            )

        score_limit = data.get('score_limit')
        if score_limit is not None:
            total_points = sum(qt['count'] * qt['points'] for qt in question_types_details)
            if total_points != score_limit:
                raise ValidationError(
                    f'Sum of points ({total_points}) must match score limit ({score_limit})'
                )
    
    @validates_schema
    def validate_modules(self, data, **kwargs):
        """Validate that modules are provided and have teaching hours"""
        if not data.get('modules'):
            raise ValidationError('At least one module is required')

        mode = data.get('module_coverage_mode', 'hours')
        modules = data['modules']
        total_hours = sum(m['teaching_hours'] for m in modules)
        if not isclose(total_hours, float(data.get('total_hours', 0) or 0), rel_tol=0.0, abs_tol=0.05):
            raise ValidationError('Total hours mismatch')

        if mode == 'percent':
            for module in modules:
                coverage = module.get('teaching_hours', 0)
                if coverage < 0 or coverage > 100:
                    raise ValidationError('Module coverage must be between 0 and 100')
        else:
            # Validate sufficient teaching hours
            num_questions = data.get('num_questions', 0)
            if num_questions > total_hours:
                raise ValidationError(
                    f'Insufficient teaching hours ({total_hours}) for {num_questions} questions'
                )

    @validates_schema
    def validate_module_question_targets(self, data, **kwargs):
        targets = data.get('module_question_targets') or []
        if not targets:
            return

        modules = data.get('modules') or []
        module_ids = {m['module_id'] for m in modules}
        target_module_ids = {t['module_id'] for t in targets}
        if target_module_ids != module_ids:
            raise ValidationError('Module question targets must include all selected modules')

        total_target_questions = sum(t['count'] for t in targets)
        if total_target_questions != data.get('num_questions', 0):
            raise ValidationError('Module question target total must match total questions')

    @validates_schema
    def validate_duration_alignment(self, data, **kwargs):
        allocated_minutes = data.get('allocated_minutes')
        duration_minutes = data.get('duration_minutes')
        if allocated_minutes is None or duration_minutes is None:
            return
        if allocated_minutes > duration_minutes:
            raise ValidationError(
                f'Allocated time ({allocated_minutes}) must not exceed duration ({duration_minutes})'
            )


class ExamUpdateSchema(Schema):
    title = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str()
    module_id = fields.Int()
    category_id = fields.Int()
    start_time = fields.DateTime(allow_none=True)
    end_time = fields.DateTime(allow_none=True)
    duration_minutes = fields.Int()
    total_questions = fields.Int()
    passing_score = fields.Int()
    is_published = fields.Bool()


class ExamSubmitSchema(Schema):
    exam_id = fields.Int(required=True)
    instructor_notes = fields.Str(missing="")
    department_id = fields.Int(missing=None, allow_none=True)  # Allow department_id from frontend


class ExamApproveSchema(Schema):
    exam_id = fields.Int(required=True)
    status = fields.Str(required=True, validate=validate.OneOf(['approved', 'rejected', 'revision_required']))
    feedback = fields.Str(missing="")


class ExamSendToDepartmentSchema(Schema):
    exam_id = fields.Int(required=True)
    department_id = fields.Int(required=True)
    notes = fields.Str(missing="")


class QuestionCreateSchema(Schema):
    question_text = fields.Str(required=True)
    question_type = fields.Str(required=True, validate=validate.OneOf([
        'factual', 'conceptual', 'procedural', 'problem_solving', 'analysis',
        'multiple_choice', 'true_false', 'modified_true_false', 'fill_in_blank',
        'identification'
    ]))
    difficulty_level = fields.Str(required=True, validate=validate.OneOf(['easy', 'medium', 'hard']))
    options = fields.List(fields.Str(), missing=[])
    correct_answer = fields.Str(required=True)
    points = fields.Int(missing=1)
    bloom_level = fields.Str(missing='remembering')


class QuestionUpdateSchema(Schema):
    question_text = fields.Str()
    question_type = fields.Str(validate=validate.OneOf([
        'factual', 'conceptual', 'procedural', 'problem_solving', 'analysis',
        'multiple_choice', 'true_false', 'modified_true_false', 'fill_in_blank',
        'identification'
    ]))
    difficulty_level = fields.Str(validate=validate.OneOf(['easy', 'medium', 'hard']))
    options = fields.List(fields.Str())
    correct_answer = fields.Str()
    points = fields.Int()
    bloom_level = fields.Str()
    image_id = fields.Int(allow_none=True)


# =====================================================================
# FIX: Define ExamAnswerCreateSchema BEFORE ExamSubmissionCreateSchema
# and use DIRECT class reference instead of string reference
# =====================================================================

class ExamAnswerCreateSchema(Schema):
    question_id = fields.Int(required=True)
    # FIX: answer_text should NOT be required - student may skip questions
    answer_text = fields.Str(missing="", allow_none=True)


class ExamSubmissionCreateSchema(Schema):
    exam_id = fields.Int(required=True)
    # FIX: Use direct class reference instead of string 'ExamAnswerCreateSchema'
    # String references can fail silently in some marshmallow versions
    answers = fields.List(fields.Nested(ExamAnswerCreateSchema), required=True)
