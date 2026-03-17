from app.database import db
from datetime import datetime


class Exam(db.Model):
    __tablename__ = 'exams'
    __table_args__ = (
        db.Index('ix_exams_module_id', 'module_id'),
        db.Index('ix_exams_teacher_id', 'teacher_id'),
        db.Index('ix_exams_category_id', 'category_id'),
        db.Index('ix_exams_department_id', 'department_id'),
        db.Index('ix_exams_admin_status', 'admin_status'),
        db.Index('ix_exams_is_published', 'is_published'),
        db.Index('ix_exams_reviewed_by', 'reviewed_by'),
        db.Index('ix_exams_teacher_status', 'teacher_id', 'admin_status'),
        {'extend_existing': True},
    )

    exam_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.module_id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('exam_categories.category_id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    total_questions = db.Column(db.Integer, nullable=True)
    passing_score = db.Column(db.Integer, nullable=True)
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Approval workflow fields
    submitted_to_admin = db.Column(db.Boolean, default=False)
    admin_status = db.Column(db.Enum('draft', 'pending', 'approved', 'rejected', 'revision_required', 'Re-Used'), default='draft')
    submitted_at = db.Column(db.DateTime, nullable=True)
    instructor_notes = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    admin_feedback = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Department approval fields
    sent_to_department = db.Column(db.Boolean, default=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.department_id'), nullable=True)
    department_notes = db.Column(db.Text, nullable=True)
    sent_to_department_at = db.Column(db.DateTime, nullable=True)

    # Re-use tracking
    reused_from_exam_id = db.Column(db.Integer, nullable=True)
    reused_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    module = db.relationship('Module', backref='exams')
    teacher = db.relationship('User', backref='created_exams', foreign_keys=[teacher_id])
    reviewer = db.relationship('User', backref='reviewed_exams', foreign_keys=[reviewed_by])
    category = db.relationship('ExamCategory', backref='exams')
    department = db.relationship('Department', backref='exams')
    # CASCADE: exam questions are derived data — delete with exam
    questions = db.relationship(
        'ExamQuestion', backref='exam',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    # CASCADE: exam_modules junction rows — delete with exam
    exam_modules = db.relationship(
        'ExamModule', backref='exam',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    # NO CASCADE on submissions — audit/history data preserved
    submissions = db.relationship('ExamSubmission', backref='exam')

    def to_dict(self):
        return {
            'exam_id': self.exam_id,
            'title': self.title,
            'description': self.description,
            'module_id': self.module_id,
            'module_title': self.module.title if self.module else None,
            'subject_id': self.module.subject_id if self.module else None,
            'subject_name': self.module.subject.subject_name if self.module and self.module.subject else None,
            'teacher_id': self.teacher_id,
            'teacher_name': f"{self.teacher.first_name} {self.teacher.last_name}" if self.teacher else None,
            'category_id': self.category_id,
            'category_name': self.category.category_name if self.category else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_minutes': self.duration_minutes,
            'total_questions': self.total_questions,
            'passing_score': self.passing_score,
            'is_published': self.is_published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'submitted_to_admin': self.submitted_to_admin,
            'admin_status': self.admin_status,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'instructor_notes': self.instructor_notes,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'admin_feedback': self.admin_feedback,
            'rejection_reason': self.rejection_reason,
            'sent_to_department': self.sent_to_department,
            'department_id': self.department_id,
            'department_name': self.department.department_name if self.department else None,
            'department_notes': self.department_notes,
            'sent_to_department_at': self.sent_to_department_at.isoformat() if self.sent_to_department_at else None,
            'reused_from_exam_id': self.reused_from_exam_id,
            'reused_at': self.reused_at.isoformat() if self.reused_at else None
        }


class SpecialExam(db.Model):
    __tablename__ = 'special_exams'
    __table_args__ = (
        db.Index('ix_special_exams_exam_id', 'exam_id'),
        db.Index('ix_special_exams_marked_by', 'marked_by'),
        {'extend_existing': True},
    )

    special_exam_id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(
        db.Integer,
        db.ForeignKey('exams.exam_id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    marked_by = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    exam = db.relationship(
        'Exam',
        backref=db.backref('special_entry', uselist=False, passive_deletes=True),
    )
    marker = db.relationship('User', backref='special_exams_marked')

    def to_dict(self):
        return {
            'special_exam_id': self.special_exam_id,
            'exam_id': self.exam_id,
            'marked_by': self.marked_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ExamQuestion(db.Model):
    __tablename__ = 'exam_questions'
    __table_args__ = (
        db.Index('ix_exam_questions_exam_id', 'exam_id'),
        db.Index('ix_exam_questions_module_question_id', 'module_question_id'),
        db.Index('ix_exam_questions_question_type', 'question_type'),
        db.Index('ix_exam_questions_difficulty', 'difficulty_level'),
        db.Index('ix_exam_questions_image_id', 'image_id'),
        {'extend_existing': True},
    )

    question_id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(
        db.Integer,
        db.ForeignKey('exams.exam_id', ondelete='CASCADE'),
        nullable=False,
    )
    module_question_id = db.Column(
        db.Integer,
        db.ForeignKey('module_questions.question_id', ondelete='SET NULL'),
        nullable=True,
    )
    question_text = db.Column(db.Text, nullable=False)
    section_instruction = db.Column(db.Text, nullable=True)
    question_type = db.Column(db.Enum('factual', 'conceptual', 'procedural', 'problem_solving', 'analysis', 'multiple_choice', 'true_false', 'modified_true_false', 'fill_in_blank', 'identification', 'short_answer', 'essay'), nullable=False)
    difficulty_level = db.Column(db.Enum('easy', 'medium', 'hard'), nullable=False)
    bloom_level = db.Column(db.String(50), nullable=True, default='remembering')
    topic = db.Column(db.String(255), nullable=True, default='General')
    options = db.Column(db.Text, nullable=True)
    correct_answer = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    image_id = db.Column(
        db.Integer,
        db.ForeignKey('module_images.image_id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    module_question = db.relationship('ModuleQuestion', backref='exam_questions')
    image = db.relationship('ModuleImage', backref='exam_questions')

    def to_dict(self):
        return {
            'question_id': self.question_id,
            'exam_id': self.exam_id,
            'module_question_id': self.module_question_id,
            'question_text': self.question_text,
            'section_instruction': self.section_instruction,
            'question_type': self.question_type,
            'difficulty_level': self.difficulty_level,
            'bloom_level': self.bloom_level or 'remembering',
            'topic': self.topic or 'General',
            'cognitive_level': self.bloom_level or 'remembering',
            'options': self.options,
            'correct_answer': self.correct_answer,
            'points': self.points,
            'feedback': self.feedback,
            'image_id': self.image_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ExamCategory(db.Model):
    __tablename__ = 'exam_categories'
    __table_args__ = {'extend_existing': True}

    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'category_id': self.category_id,
            'category_name': self.category_name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ExamSubmission(db.Model):
    """Audit/history table — NOT cascaded from Exam deletion."""
    __tablename__ = 'exam_submissions'
    __table_args__ = (
        db.Index('ix_exam_submissions_exam_id', 'exam_id'),
        db.Index('ix_exam_submissions_user_id', 'user_id'),
        db.Index('ix_exam_submissions_completed', 'is_completed'),
        {'extend_existing': True},
    )

    submission_id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.exam_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    submit_time = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Integer, nullable=True)
    total_points = db.Column(db.Integer, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships — answers cascade with their submission
    user = db.relationship('User', backref='exam_submissions')
    answers = db.relationship(
        'ExamAnswer', backref='submission',
        cascade='all, delete-orphan', passive_deletes=True,
    )

    def to_dict(self):
        return {
            'submission_id': self.submission_id,
            'exam_id': self.exam_id,
            'user_id': self.user_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'submit_time': self.submit_time.isoformat() if self.submit_time else None,
            'score': self.score,
            'total_points': self.total_points,
            'is_completed': self.is_completed,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ExamAnswer(db.Model):
    __tablename__ = 'exam_answers'
    __table_args__ = (
        db.Index('ix_exam_answers_submission_id', 'submission_id'),
        db.Index('ix_exam_answers_question_id', 'question_id'),
        {'extend_existing': True},
    )

    answer_id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer,
        db.ForeignKey('exam_submissions.submission_id', ondelete='CASCADE'),
        nullable=False,
    )
    question_id = db.Column(db.Integer, db.ForeignKey('exam_questions.question_id'), nullable=False)
    answer_text = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    points_earned = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    question = db.relationship('ExamQuestion', backref='answers')

    def to_dict(self):
        return {
            'answer_id': self.answer_id,
            'submission_id': self.submission_id,
            'question_id': self.question_id,
            'answer_text': self.answer_text,
            'is_correct': self.is_correct,
            'points_earned': self.points_earned,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ExamModule(db.Model):
    """Many-to-many association: tracks which modules were used to generate each exam."""
    __tablename__ = 'exam_modules'
    __table_args__ = (
        db.Index('ix_exam_modules_exam_id', 'exam_id'),
        db.Index('ix_exam_modules_module_id', 'module_id'),
        {'extend_existing': True},
    )

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    exam_id    = db.Column(
        db.Integer,
        db.ForeignKey('exams.exam_id', ondelete='CASCADE'),
        nullable=False,
    )
    module_id  = db.Column(db.Integer, db.ForeignKey('modules.module_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    module = db.relationship('Module', backref='exam_modules')

    def to_dict(self):
        return {
            'id':        self.id,
            'exam_id':   self.exam_id,
            'module_id': self.module_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
