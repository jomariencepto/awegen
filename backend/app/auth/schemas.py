from marshmallow import Schema, fields, validate, validates, ValidationError
import re


class UserSchema(Schema):
    """Schema for User serialization"""
    user_id = fields.Int(dump_only=True)
    username = fields.Str(required=True)
    email = fields.Email(required=True)
    first_name = fields.Str(allow_none=True)
    last_name = fields.Str(allow_none=True)
    role = fields.Str(allow_none=True)
    role_id = fields.Int(allow_none=True)
    department_id = fields.Int(allow_none=True)
    school_id_number = fields.Int(allow_none=True)
    is_active = fields.Bool(dump_only=True)
    is_verified = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class UserRegistrationSchema(Schema):
    """Schema for user registration"""
    username = fields.Str(
        required=True,
        validate=validate.Length(min=3, max=80),
        error_messages={'required': 'Username is required'}
    )
    email = fields.Email(
        required=True,
        error_messages={'required': 'Email is required'}
    )
    password = fields.Str(
        required=True,
        validate=validate.Length(min=8),
        load_only=True,
        error_messages={'required': 'Password is required'}
    )
    confirm_password = fields.Str(
        required=True,
        load_only=True,
        error_messages={'required': 'Confirm password is required'}
    )
    first_name = fields.Str(validate=validate.Length(max=50))
    last_name = fields.Str(validate=validate.Length(max=50))
    role = fields.Str(validate=validate.OneOf(['admin', 'teacher', 'student']))
    department_id = fields.Int(allow_none=True)
    school_id_number = fields.Int(allow_none=True)
    
    @validates('password')
    def validate_password(self, value):
        """Validate password strength"""
        if len(value) < 8:
            raise ValidationError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', value):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', value):
            raise ValidationError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', value):
            raise ValidationError('Password must contain at least one number')


class UserLoginSchema(Schema):
    """Schema for user login"""
    username = fields.Str(required=True, error_messages={'required': 'Username is required'})
    password = fields.Str(required=True, load_only=True, error_messages={'required': 'Password is required'})


class OTPRequestSchema(Schema):
    """Schema for OTP request"""
    email = fields.Email(required=True, error_messages={'required': 'Email is required'})
    purpose = fields.Str(
        required=True,
        validate=validate.OneOf(['registration', 'password_reset', 'email_verification']),
        error_messages={'required': 'Purpose is required'}
    )


class OTPVerifySchema(Schema):
    """Schema for OTP verification"""
    email = fields.Email(required=True, error_messages={'required': 'Email is required'})
    otp_code = fields.Str(
        required=True,
        validate=validate.Length(equal=6),
        error_messages={'required': 'OTP code is required'}
    )
    purpose = fields.Str(required=True, error_messages={'required': 'Purpose is required'})


class OTPVerificationSchema(Schema):
    """Schema for OTP verification serialization"""
    id = fields.Int(dump_only=True)
    user_id = fields.Int(required=True)
    email = fields.Email(required=True)
    otp_code = fields.Str(dump_only=True)
    purpose = fields.Str(required=True)
    is_used = fields.Bool(dump_only=True)
    expires_at = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class PasswordResetSchema(Schema):
    """Schema for password reset"""
    email = fields.Email(required=True, error_messages={'required': 'Email is required'})
    otp_code = fields.Str(
        required=True,
        validate=validate.Length(equal=6),
        error_messages={'required': 'OTP code is required'}
    )
    new_password = fields.Str(
        required=True,
        validate=validate.Length(min=8),
        load_only=True,
        error_messages={'required': 'New password is required'}
    )
    confirm_password = fields.Str(
        required=True,
        load_only=True,
        error_messages={'required': 'Confirm password is required'}
    )
    
    @validates('new_password')
    def validate_password(self, value):
        """Validate password strength"""
        if len(value) < 8:
            raise ValidationError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', value):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', value):
            raise ValidationError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', value):
            raise ValidationError('Password must contain at least one number')