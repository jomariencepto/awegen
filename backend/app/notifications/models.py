# app/notifications/models.py
from datetime import datetime
from app.database import db


class Notification(db.Model):
    __tablename__ = 'notifications'
    __table_args__ = {'extend_existing': True}  # Use existing table
    
    # Match your exact table structure
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # No relationship definition here - it's defined in the User model
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'message': self.text,  # Keep 'message' for API consistency
            'is_read': self.read,   # Keep 'is_read' for API consistency
            'created_at': self.created_at.isoformat() if self.created_at else None
        }