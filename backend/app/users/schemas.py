from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from app.users.models import Department, School, Subject
from app.auth.models import User


class DepartmentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Department
        load_instance = True
        include_fk = True


class SchoolSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = School
        load_instance = True


class SubjectSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Subject
        load_instance = True
        include_fk = True


class UserUpdateSchema(Schema):
    first_name = fields.Str(validate=validate.Length(min=2))
    last_name = fields.Str(validate=validate.Length(min=2))
    department_id = fields.Int()
    school_id_number = fields.Str()
    is_active = fields.Bool()


class UserApprovalSchema(Schema):
    user_id = fields.Int(required=True)
    is_approved = fields.Bool(required=True)