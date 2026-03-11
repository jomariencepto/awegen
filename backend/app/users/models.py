from app.database import db
from app.auth.models import User


class Department(db.Model):
    __tablename__ = 'departments'
    __table_args__ = (
        db.Index('ix_departments_school_id', 'school_id_number'),
        {'extend_existing': True},
    )

    department_id = db.Column(db.Integer, primary_key=True)
    school_id_number = db.Column(db.Integer, db.ForeignKey('schools.school_id_number'), nullable=False)
    department_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationships
    school = db.relationship('School', backref='departments')
    
    def to_dict(self):
        return {
            'department_id': self.department_id,
            'school_id_number': self.school_id_number,
            'department_name': self.department_name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class School(db.Model):
    __tablename__ = 'schools'
    
    school_id_number = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=True)
    contact_email = db.Column(db.String(100), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def to_dict(self):
        return {
            'school_id_number': self.school_id_number,
            'school_name': self.school_name,
            'address': self.address,
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Subject(db.Model):
    __tablename__ = 'subjects'
    __table_args__ = (
        db.Index('ix_subjects_department_id', 'department_id'),
        {'extend_existing': True},
    )

    subject_id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(100), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.department_id'), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationships
    department = db.relationship('Department', backref='subjects')
    
    def to_dict(self):
        return {
            'subject_id': self.subject_id,
            'subject_name': self.subject_name,
            'department_id': self.department_id,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }