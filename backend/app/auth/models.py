from app.database import db
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets


class Role(db.Model):
    __tablename__ = 'roles'
    __table_args__ = {'extend_existing': True}

    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'role_id': self.role_id,
            'role_name': self.role_name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        db.Index('ix_users_role', 'role'),
        db.Index('ix_users_role_id', 'role_id'),
        db.Index('ix_users_department_id', 'department_id'),
        db.Index('ix_users_school_id', 'school_id_number'),
        db.Index('ix_users_is_active', 'is_active'),
        db.Index('ix_users_is_approved', 'is_approved'),
        {'extend_existing': True},
    )

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='teacher')
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.department_id'), nullable=True)
    department_name = db.Column(db.String(100), nullable=True)
    school_id_number = db.Column(db.Integer, db.ForeignKey('schools.school_id_number'), nullable=True)
    is_approved = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    role_obj = db.relationship('Role', backref='users')
    department = db.relationship('Department', backref='users', foreign_keys=[department_id])
    school = db.relationship('School', backref='users')
    # CASCADE ephemeral auth data when user is deleted
    refresh_tokens = db.relationship(
        'RefreshToken', backref='user',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    otp_verifications = db.relationship(
        'OTPVerification', backref='user',
        cascade='all, delete-orphan', passive_deletes=True,
    )
    notifications = db.relationship(
        'Notification', backref='user',
        cascade='all, delete-orphan',
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        resolved_department_name = self.department_name
        if not resolved_department_name and self.department:
            resolved_department_name = self.department.department_name

        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role': self.role,
            'role_id': self.role_id,
            'department_id': self.department_id,
            'department_name': resolved_department_name,
            'school_id_number': self.school_id_number,
            'is_approved': self.is_approved,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'
    __table_args__ = (
        db.Index('ix_refresh_tokens_user_id', 'user_id'),
        {'extend_existing': True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=False,
    )
    token = db.Column(db.String(500), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class OTPVerification(db.Model):
    __tablename__ = 'otp_verifications'
    __table_args__ = (
        db.Index('ix_otp_verifications_user_id', 'user_id'),
        db.Index('ix_otp_verifications_email', 'email'),
        {'extend_existing': True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=False,
    )
    email = db.Column(db.String(120), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    purpose = db.Column(db.String(50), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_otp():
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])

    def is_valid(self):
        return not self.is_used and datetime.utcnow() < self.expires_at

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'purpose': self.purpose,
            'is_used': self.is_used,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
