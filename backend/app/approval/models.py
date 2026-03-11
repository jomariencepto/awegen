from app.database import db
from datetime import datetime


class TeacherApproval(db.Model):
    """Audit table — NO cascade from User deletion."""
    __tablename__ = 'teacher_approvals'
    __table_args__ = (
        db.Index('ix_teacher_approvals_user_id', 'user_id'),
        db.Index('ix_teacher_approvals_approved_by', 'approved_by'),
        db.Index('ix_teacher_approvals_status', 'status'),
        {'extend_existing': True},
    )

    approval_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    department_name = db.Column(db.String(100), nullable=True)
    status = db.Column(db.Enum('pending', 'approved', 'rejected'), default='pending')
    rejection_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='approvals', foreign_keys=[user_id])
    approver = db.relationship('User', backref='approved_approvals', foreign_keys=[approved_by])
    
    def to_dict(self):
        return {
            'approval_id': self.approval_id,
            'user_id': self.user_id,
            'approved_by': self.approved_by,
            'department_name': self.department_name,
            'status': self.status,
            'rejection_reason': self.rejection_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }