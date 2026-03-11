from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from app.notifications.models import Notification  # Changed import location
from app.approval.models import TeacherApproval


class NotificationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Notification
        load_instance = True


class TeacherApprovalSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = TeacherApproval
        load_instance = True
        include_fk = True


class NotificationCreateSchema(Schema):
    user_id = fields.Int(required=True)
    type = fields.Str(required=True)
    text = fields.Str(required=True)


class NotificationUpdateSchema(Schema):
    read = fields.Bool(required=True)


class TeacherApprovalCreateSchema(Schema):
    user_id = fields.Int(required=True)
    department_name = fields.Str(required=True)


class TeacherApprovalUpdateSchema(Schema):
    status = fields.Str(required=True, validate=validate.OneOf(['approved', 'rejected']))
    rejection_reason = fields.Str(missing="")