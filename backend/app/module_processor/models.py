from app.database import db
from datetime import datetime


class Module(db.Model):
    __tablename__ = 'modules'
    __table_args__ = (
        db.Index('ix_modules_teacher_id', 'teacher_id'),
        db.Index('ix_modules_subject_id', 'subject_id'),
        db.Index('ix_modules_processing_status', 'processing_status'),
        db.Index('ix_modules_is_archived', 'is_archived'),
        db.Index('ix_modules_teacher_status', 'teacher_id', 'processing_status'),
        {'extend_existing': True},
    )

    module_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.subject_id'), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(512), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    processing_status = db.Column(db.Enum('pending', 'processing', 'completed', 'failed'), default='pending')
    teaching_hours = db.Column(db.Integer, nullable=True)
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships — cascade derived data when module is deleted
    teacher = db.relationship('User', backref='modules')
    subject = db.relationship('Subject', backref='modules')
    contents = db.relationship(
        'ModuleContent', backref='module',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    summaries = db.relationship(
        'ModuleSummary', backref='module',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    keywords = db.relationship(
        'ModuleKeyword', backref='module',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    topics = db.relationship(
        'ModuleTopic', backref='module',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    entities = db.relationship(
        'ModuleEntity', backref='module',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    images = db.relationship(
        'ModuleImage', backref='module',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    questions = db.relationship(
        'ModuleQuestion', backref='module',
        cascade='all, delete-orphan', passive_deletes=True,
    )

    def to_dict(self):
        return {
            'module_id': self.module_id,
            'title': self.title,
            'description': self.description,
            'teacher_id': self.teacher_id,
            'teacher_name': f"{self.teacher.first_name} {self.teacher.last_name}" if self.teacher else None,
            'subject_id': self.subject_id,
            'subject_name': self.subject.subject_name if self.subject else None,
            'upload_date': self.upload_date.isoformat() if self.upload_date else None,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'processing_status': self.processing_status,
            'teaching_hours': self.teaching_hours,
            'is_archived': self.is_archived,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ModuleContent(db.Model):
    __tablename__ = 'module_content'
    __table_args__ = (
        db.Index('ix_module_content_module_id', 'module_id'),
        {'extend_existing': True},
    )

    content_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_id = db.Column(
        db.Integer,
        db.ForeignKey('modules.module_id', ondelete='CASCADE'),
        nullable=False,
    )
    section_title = db.Column(db.String(255), nullable=True)
    content_order = db.Column(db.Integer, nullable=False)
    content_text = db.Column(db.Text, nullable=False)
    content_type = db.Column(db.Enum('heading', 'paragraph', 'list', 'code', 'image_caption', 'table_caption'), default='paragraph')
    word_count = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'content_id': self.content_id,
            'module_id': self.module_id,
            'section_title': self.section_title,
            'content_order': self.content_order,
            'content_text': self.content_text,
            'content_type': self.content_type,
            'word_count': self.word_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ModuleSummary(db.Model):
    __tablename__ = 'module_summaries'
    __table_args__ = (
        db.Index('ix_module_summaries_module_id', 'module_id'),
        {'extend_existing': True},
    )

    summary_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_id = db.Column(
        db.Integer,
        db.ForeignKey('modules.module_id', ondelete='CASCADE'),
        nullable=False,
    )
    summary_text = db.Column(db.Text, nullable=False)
    summary_type = db.Column(db.Enum('extractive', 'abstractive', 'hybrid'), default='extractive')
    word_count = db.Column(db.Integer, nullable=True)
    key_points = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'summary_id': self.summary_id,
            'module_id': self.module_id,
            'summary_text': self.summary_text,
            'summary_type': self.summary_type,
            'word_count': self.word_count,
            'key_points': self.key_points,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ModuleKeyword(db.Model):
    __tablename__ = 'module_keywords'
    __table_args__ = (
        db.Index('ix_module_keywords_module_id', 'module_id'),
        {'extend_existing': True},
    )

    keyword_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_id = db.Column(
        db.Integer,
        db.ForeignKey('modules.module_id', ondelete='CASCADE'),
        nullable=False,
    )
    keyword = db.Column(db.String(100), nullable=False)
    keyword_type = db.Column(db.Enum('technical_term', 'concept', 'definition', 'example', 'other'), default='technical_term')
    relevance_score = db.Column(db.Numeric(5, 3), default=1.000)
    frequency = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'keyword_id': self.keyword_id,
            'module_id': self.module_id,
            'keyword': self.keyword,
            'keyword_type': self.keyword_type,
            'relevance_score': float(self.relevance_score) if self.relevance_score else None,
            'frequency': self.frequency,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ModuleTopic(db.Model):
    __tablename__ = 'module_topics'
    __table_args__ = (
        db.Index('ix_module_topics_module_id', 'module_id'),
        {'extend_existing': True},
    )

    topic_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_id = db.Column(
        db.Integer,
        db.ForeignKey('modules.module_id', ondelete='CASCADE'),
        nullable=False,
    )
    topic_name = db.Column(db.String(255), nullable=False)
    topic_weight = db.Column(db.Numeric(5, 3), default=1.000)
    frequency = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'topic_id': self.topic_id,
            'module_id': self.module_id,
            'topic_name': self.topic_name,
            'topic_weight': float(self.topic_weight) if self.topic_weight else None,
            'frequency': self.frequency,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ModuleEntity(db.Model):
    __tablename__ = 'module_entities'
    __table_args__ = (
        db.Index('ix_module_entities_module_id', 'module_id'),
        db.Index('ix_module_entities_entity_type', 'entity_type'),
        {'extend_existing': True},
    )

    entity_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_id = db.Column(
        db.Integer,
        db.ForeignKey('modules.module_id', ondelete='CASCADE'),
        nullable=False,
    )
    entity_text = db.Column(db.String(255), nullable=False)
    entity_type = db.Column(db.Enum('PERSON', 'ORGANIZATION', 'LOCATION', 'DATE', 'TIME', 'MONEY', 'PERCENT', 'FACILITY', 'GPE', 'PRODUCT', 'EVENT', 'WORK_OF_ART', 'LANGUAGE', 'LAW', 'OTHER'), default='OTHER')
    start_position = db.Column(db.Integer, nullable=True)
    end_position = db.Column(db.Integer, nullable=True)
    confidence_score = db.Column(db.Numeric(5, 3), default=1.000)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'entity_id': self.entity_id,
            'module_id': self.module_id,
            'entity_text': self.entity_text,
            'entity_type': self.entity_type,
            'start_position': self.start_position,
            'end_position': self.end_position,
            'confidence_score': float(self.confidence_score) if self.confidence_score else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ModuleImage(db.Model):
    __tablename__ = 'module_images'
    __table_args__ = (
        db.Index('ix_module_images_module_id', 'module_id'),
        {'extend_existing': True},
    )

    image_id    = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_id   = db.Column(
        db.Integer,
        db.ForeignKey('modules.module_id', ondelete='CASCADE'),
        nullable=False,
    )
    image_path  = db.Column(db.String(500), nullable=False)
    page_number = db.Column(db.Integer, nullable=True)
    image_index = db.Column(db.Integer, nullable=True)
    width       = db.Column(db.Integer, nullable=True)
    height      = db.Column(db.Integer, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'image_id':    self.image_id,
            'module_id':   self.module_id,
            'image_path':  self.image_path,
            'page_number': self.page_number,
            'image_index': self.image_index,
            'width':       self.width,
            'height':      self.height,
            'created_at':  self.created_at.isoformat() if self.created_at else None,
        }


class ModuleQuestion(db.Model):
    __tablename__ = 'module_questions'
    __table_args__ = (
        db.Index('ix_module_questions_module_id', 'module_id'),
        db.Index('ix_module_questions_question_type', 'question_type'),
        db.Index('ix_module_questions_difficulty', 'difficulty_level'),
        db.Index('ix_module_questions_image_id', 'image_id'),
        {'extend_existing': True},
    )

    question_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_id = db.Column(
        db.Integer,
        db.ForeignKey('modules.module_id', ondelete='CASCADE'),
        nullable=False,
    )
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.Enum('factual', 'conceptual', 'procedural', 'problem_solving', 'analysis'), default='factual')
    difficulty_level = db.Column(db.Enum('easy', 'medium', 'hard'), default='medium')
    correct_answer = db.Column(db.Text, nullable=True)
    topic = db.Column(db.String(255), nullable=True)
    created_by_nlp = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    image_id = db.Column(
        db.Integer,
        db.ForeignKey('module_images.image_id', ondelete='SET NULL'),
        nullable=True,
    )

    # Relationships
    image = db.relationship('ModuleImage', backref='questions')

    def to_dict(self):
        return {
            'question_id': self.question_id,
            'module_id': self.module_id,
            'question_text': self.question_text,
            'question_type': self.question_type,
            'difficulty_level': self.difficulty_level,
            'topic': self.topic,
            'created_by_nlp': self.created_by_nlp,
            'correct_answer': self.correct_answer,
            'image_id': self.image_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
