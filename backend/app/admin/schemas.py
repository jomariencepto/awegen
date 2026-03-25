from marshmallow import Schema, fields, validate


class AdminCreateUserSchema(Schema):
    """Schema for admin-managed teacher and department-head accounts."""

    first_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=50),
        error_messages={'required': 'First name is required'},
    )
    last_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=50),
        error_messages={'required': 'Last name is required'},
    )
    email = fields.Email(
        required=True,
        error_messages={'required': 'Email is required'},
    )
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=8),
        error_messages={'required': 'Password is required'},
    )
    role = fields.Str(
        required=True,
        validate=validate.OneOf(['teacher', 'department_head']),
        error_messages={'required': 'Role is required'},
    )
    school_id_number = fields.Int(
        required=True,
        error_messages={'required': 'School is required'},
    )
    department_id = fields.Int(
        required=True,
        error_messages={'required': 'Department is required'},
    )
    subject_ids = fields.List(
        fields.Int(strict=True),
        load_default=list,
    )
    is_active = fields.Bool(load_default=True)


class AdminAssignTeacherSubjectsSchema(Schema):
    subject_ids = fields.List(
        fields.Int(strict=True),
        required=True,
    )
