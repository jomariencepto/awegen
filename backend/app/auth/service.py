import traceback
import re
from datetime import datetime, timedelta
from app.database import db
from app.auth.models import User, OTPVerification, RefreshToken, Role
from app.notifications.models import Notification
from werkzeug.security import generate_password_hash
import random
import string
import logging

logger = logging.getLogger(__name__)


class AuthService:
    NAME_PATTERN = re.compile(r"^[A-Za-z\s'-]+$")
    REGISTRATION_OTP_TTL_MINUTES = 10
    OTP_RESEND_INTERVAL_SECONDS = 120  # 2 minutes cooldown per resend
    
    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def generate_username(email):
        """Generate username from email"""
        return email.split('@')[0]

    @staticmethod
    def _registration_deadline(user):
        if not user or not user.created_at:
            return None
        return user.created_at + timedelta(minutes=AuthService.REGISTRATION_OTP_TTL_MINUTES)

    @staticmethod
    def _is_registration_expired(user, now=None):
        if not user or user.is_verified:
            return False
        deadline = AuthService._registration_deadline(user)
        if not deadline:
            return False
        now = now or datetime.utcnow()
        return now >= deadline

    @staticmethod
    def _purge_expired_unverified_registration(email=None, user=None):
        """
        Remove registration accounts that were not OTP-verified within 10 minutes.
        Some deployments still have non-cascading user foreign keys in MySQL, so
        direct dependents are removed explicitly before deleting the user record.
        Returns number of removed users.
        """
        now = datetime.utcnow()
        removed = 0

        if user is not None:
            candidates = [user]
        elif email:
            candidates = User.query.filter_by(email=email).all()
        else:
            return 0

        for candidate in candidates:
            if AuthService._is_registration_expired(candidate, now=now):
                deleted_notifications = Notification.query.filter_by(user_id=candidate.user_id).delete(
                    synchronize_session=False
                )
                deleted_otps = OTPVerification.query.filter_by(user_id=candidate.user_id).delete(
                    synchronize_session=False
                )
                deleted_refresh_tokens = RefreshToken.query.filter_by(user_id=candidate.user_id).delete(
                    synchronize_session=False
                )
                logger.info(
                    "🧹 Removing expired unverified registration for %s (created_at=%s, deadline=%s, notifications=%s, otp_verifications=%s, refresh_tokens=%s)",
                    candidate.email,
                    candidate.created_at,
                    AuthService._registration_deadline(candidate),
                    deleted_notifications,
                    deleted_otps,
                    deleted_refresh_tokens,
                )
                db.session.delete(candidate)
                removed += 1

        if removed > 0:
            db.session.commit()

        return removed

    @staticmethod
    def _otp_resend_remaining_seconds(email, purpose):
        """
        Return remaining cooldown seconds before another OTP can be sent.
        Zero means resend is allowed.
        """
        latest_otp = (
            OTPVerification.query.filter_by(email=email, purpose=purpose)
            .order_by(OTPVerification.created_at.desc(), OTPVerification.id.desc())
            .first()
        )
        if not latest_otp:
            return 0

        created_at = latest_otp.created_at
        if not created_at and latest_otp.expires_at:
            created_at = latest_otp.expires_at - timedelta(
                minutes=AuthService.REGISTRATION_OTP_TTL_MINUTES
            )
        if not created_at:
            return 0

        elapsed = (datetime.utcnow() - created_at).total_seconds()
        remaining = int(AuthService.OTP_RESEND_INTERVAL_SECONDS - elapsed)
        return max(remaining, 0)
    
    @staticmethod
    def validate_strong_password(password):
        """
        Validate password strength
        Returns (is_valid, error_message)
        
        Requirements:
        - Minimum 8 characters
        - At least one uppercase letter (A-Z)
        - At least one lowercase letter (a-z)
        - At least one number (0-9)
        - At least one special character (!@#$%^&*(),.?":{}|<>)
        """
        logger.info("🔐 Validating password strength...")
        
        if len(password) < 8:
            logger.warning("❌ Password too short")
            return False, "Password must be at least 8 characters long"
        
        if not re.search(r'[A-Z]', password):
            logger.warning("❌ Password missing uppercase letter")
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            logger.warning("❌ Password missing lowercase letter")
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'\d', password):
            logger.warning("❌ Password missing number")
            return False, "Password must contain at least one number"
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            logger.warning("❌ Password missing special character")
            return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
        
        logger.info("✅ Password meets all strength requirements")
        return True, None
    
    @staticmethod
    def register_user(data):
        """Register a new user with comprehensive error handling"""
        try:
            if not isinstance(data, dict):
                return {'success': False, 'message': 'Invalid registration payload'}, 400

            # ⭐ STEP 1: Extract and log all data
            email = (data.get('email') or '').strip().lower()
            password = data.get('password')
            first_name = (data.get('first_name') or '').strip()
            last_name = (data.get('last_name') or '').strip()
            role_id = data.get('role_id')
            school_id_number = data.get('school_id_number')
            department_id = data.get('department_id')
            department = None
            
            logger.info("="*60)
            logger.info(f"🔐 REGISTRATION ATTEMPT")
            logger.info("="*60)
            logger.info(f"📧 Email: {email}")
            logger.info(f"👤 Name: {first_name} {last_name}")
            logger.info(f"🎭 Role ID: {role_id}")
            logger.info(f"🏫 School ID: {school_id_number}")
            logger.info(f"🏢 Department ID: {department_id}")
            logger.info("="*60)
            
            # ⭐ STEP 2: Validate ONLY universal required fields
            # NOTE: school_id_number and department_id are role-dependent
            universal_required = ['email', 'password', 'first_name', 'last_name', 'role_id']
            missing_fields = [field for field in universal_required if not data.get(field)]
            
            if missing_fields:
                error_msg = f'Missing required fields: {", ".join(missing_fields)}'
                logger.error(f"❌ {error_msg}")
                return {'success': False, 'message': error_msg}, 400
            
            logger.info("✅ Universal required fields present")

            # ⭐ STEP 2.1: Validate basic identity fields
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                return {'success': False, 'message': 'Invalid email format'}, 400
            if len(first_name) > 50 or not AuthService.NAME_PATTERN.match(first_name):
                return {'success': False, 'message': 'First name must contain letters only'}, 400
            if len(last_name) > 50 or not AuthService.NAME_PATTERN.match(last_name):
                return {'success': False, 'message': 'Last name must contain letters only'}, 400
             
            # ⭐ STEP 2.5: VALIDATE STRONG PASSWORD
            is_valid, error_message = AuthService.validate_strong_password(password)
            if not is_valid:
                logger.error(f"❌ Password validation failed: {error_message}")
                return {'success': False, 'message': error_message}, 400
            
            logger.info("✅ Password meets strength requirements")
            
            # ⭐ STEP 2.6: Check role-based requirements
            try:
                role_id_int = int(role_id)
                role_id = role_id_int
                logger.info(f"🎭 Checking role-based requirements for role_id: {role_id_int}")
                
                if role_id_int == 1:
                    # Admin - School REQUIRED, NO department
                    logger.info("✅ Admin role - school required, department optional")
                    if not school_id_number:
                        error_msg = 'School is required for Admin users'
                        logger.error(f"❌ {error_msg}")
                        return {'success': False, 'message': error_msg}, 400
                    
                elif role_id_int == 2:
                    # Teacher - School AND Department REQUIRED
                    logger.info("✅ Teacher role - school and department required")
                    if not school_id_number:
                        error_msg = 'School is required for Teacher users'
                        logger.error(f"❌ {error_msg}")
                        return {'success': False, 'message': error_msg}, 400
                    if not department_id:
                        error_msg = 'Department is required for Teacher users'
                        logger.error(f"❌ {error_msg}")
                        return {'success': False, 'message': error_msg}, 400
                    
                elif role_id_int == 3:
                    # Department Head - School AND Department REQUIRED
                    logger.info("✅ Department Head role - school and department required")
                    if not school_id_number:
                        error_msg = 'School is required for Department Head users'
                        logger.error(f"❌ {error_msg}")
                        return {'success': False, 'message': error_msg}, 400
                    if not department_id:
                        error_msg = 'Department is required for Department Head users'
                        logger.error(f"❌ {error_msg}")
                        return {'success': False, 'message': error_msg}, 400
                else:
                    error_msg = f'Invalid role_id: {role_id_int}'
                    logger.error(f"❌ {error_msg}")
                    return {'success': False, 'message': error_msg}, 400
                    
            except (ValueError, TypeError) as e:
                error_msg = f'Invalid role_id format: {str(e)}'
                logger.error(f"❌ {error_msg}")
                return {'success': False, 'message': error_msg}, 400
            
            # ⭐ STEP 3: Check if user already exists
            try:
                # Auto-cleanup: if previous registration was never OTP-verified
                # within 10 minutes, remove it so the same email can register again.
                AuthService._purge_expired_unverified_registration(email=email)

                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    error_msg = 'Email already registered'
                    logger.warning(f"⚠️ {error_msg}: {email}")
                    return {'success': False, 'message': error_msg}, 409
                logger.info("✅ Email is available")
            except Exception as e:
                logger.error(f"❌ Database error checking existing user: {str(e)}")
                raise
            
            # ⭐ STEP 4: Validate Role
            try:
                role = Role.query.get(role_id)
                if not role:
                    error_msg = f'Invalid role ID: {role_id}. Role does not exist in database.'
                    logger.error(f"❌ {error_msg}")
                    
                    # List available roles for debugging
                    available_roles = Role.query.all()
                    logger.info(f"📋 Available roles: {[(r.role_id, r.role_name) for r in available_roles]}")
                    
                    return {'success': False, 'message': error_msg}, 400
                
                role_name = role.role_name.lower()
                logger.info(f"✅ Valid role: {role_name} (ID: {role_id})")
            except Exception as e:
                logger.error(f"❌ Database error validating role: {str(e)}")
                raise
            
            # ⭐ STEP 5: Generate unique username
            try:
                username = AuthService.generate_username(email)
                base_username = username
                counter = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username}{counter}"
                    counter += 1
                logger.info(f"✅ Generated unique username: {username}")
            except Exception as e:
                logger.error(f"❌ Error generating username: {str(e)}")
                raise
            
            # ⭐ STEP 6: Convert and validate IDs
            try:
                # Convert school ID (only if not None)
                if school_id_number is not None:
                    if isinstance(school_id_number, str):
                        school_id_number = school_id_number.strip()
                        school_id_number = int(school_id_number) if school_id_number else None
                    else:
                        school_id_number = int(school_id_number)
                    logger.info(f"✅ School ID converted: {school_id_number}")
                else:
                    logger.info("✅ School ID is None")
                
                # Convert department ID (only if not None)
                if department_id is not None:
                    if isinstance(department_id, str):
                        department_id = department_id.strip()
                        department_id = int(department_id) if department_id else None
                    else:
                        department_id = int(department_id)
                    logger.info(f"✅ Department ID converted: {department_id}")
                else:
                    logger.info("✅ Department ID is None (Admin)")
                    
            except (TypeError, ValueError) as e:
                error_msg = f'Invalid ID format: {str(e)}'
                logger.error(f"❌ {error_msg}")
                return {'success': False, 'message': error_msg}, 400
            
            logger.info("✅ All IDs validated and converted")
            
            # ⭐ STEP 7: Validate School exists (only if not None)
            if school_id_number is not None:
                try:
                    from app.users.models import School
                    school = School.query.get(school_id_number)
                    if not school:
                        error_msg = f'Invalid school ID: {school_id_number}. School does not exist.'
                        logger.error(f"❌ {error_msg}")
                        
                        # List available schools for debugging
                        available_schools = School.query.all()
                        logger.info(f"📋 Available schools: {[(s.school_id_number, s.school_name) for s in available_schools]}")
                        
                        return {'success': False, 'message': error_msg}, 400
                    
                    logger.info(f"✅ Valid school: {school.school_name} (ID: {school_id_number})")
                except Exception as e:
                    logger.error(f"❌ Database error validating school: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise
            else:
                logger.info("ℹ️ Skipping school validation")
            
            # ⭐ STEP 8: Validate Department exists (only if not None)
            if department_id is not None:
                try:
                    from app.users.models import Department
                    department = Department.query.get(department_id)
                    if not department:
                        error_msg = f'Invalid department ID: {department_id}. Department does not exist.'
                        logger.error(f"❌ {error_msg}")
                        
                        # List available departments for debugging
                        available_depts = Department.query.all()
                        logger.info(f"📋 Available departments: {[(d.department_id, d.department_name) for d in available_depts]}")
                        
                        return {'success': False, 'message': error_msg}, 400
                    
                    logger.info(f"✅ Valid department: {department.department_name} (ID: {department_id})")
                except Exception as e:
                    logger.error(f"❌ Database error validating department: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise
            else:
                logger.info("ℹ️ Skipping department validation (Admin)")
            
            # ⭐ STEP 9: Hash password
            try:
                password_hash = generate_password_hash(password)
                logger.info("✅ Password hashed successfully")
            except Exception as e:
                logger.error(f"❌ Error hashing password: {str(e)}")
                raise
            
            # ⭐ STEP 10: Create user object
            try:
                logger.info("📝 Creating user object...")
                new_user = User(
                    email=email,
                    password_hash=password_hash,
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                    role=role_name,
                    role_id=role_id,
                    school_id_number=school_id_number,
                    department_id=department_id,  # Will be None for Admin
                    department_name=department.department_name if department else None,
                    is_verified=False,
                    is_active=True
                )
                
                logger.info("✅ User object created")
                logger.info(f"   - Email: {new_user.email}")
                logger.info(f"   - Username: {new_user.username}")
                logger.info(f"   - Role: {new_user.role} (ID: {new_user.role_id})")
                logger.info(f"   - School ID: {new_user.school_id_number or 'None'}")
                logger.info(f"   - Department ID: {new_user.department_id or 'None (Admin)'}")
            except Exception as e:
                logger.error(f"❌ Error creating user object: {str(e)}")
                logger.error(traceback.format_exc())
                raise
            
            # ⭐ STEP 11: Add to database and flush
            try:
                logger.info("💾 Adding user to database...")
                db.session.add(new_user)
                db.session.flush()  # Get the user_id
                logger.info(f"✅ User added to database with ID: {new_user.user_id}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Database error adding user: {str(e)}")
                logger.error(f"   Error type: {type(e).__name__}")
                logger.error(traceback.format_exc())
                
                # Try to provide more specific error message
                error_str = str(e).lower()
                if 'foreign key' in error_str or 'constraint' in error_str:
                    return {'success': False, 'message': 'Invalid reference data. Please contact support.'}, 400
                elif 'unique' in error_str:
                    return {'success': False, 'message': 'User with this information already exists'}, 409
                else:
                    return {'success': False, 'message': f'Database error: {str(e)}'}, 500
            
            # ⭐ STEP 12: Generate OTP
            try:
                logger.info("🔑 Generating OTP...")
                otp_code = AuthService.generate_otp()
                expires_at = datetime.utcnow() + timedelta(
                    minutes=AuthService.REGISTRATION_OTP_TTL_MINUTES
                )
                logger.info(f"✅ OTP generated: {otp_code} (expires in 10 minutes)")
            except Exception as e:
                logger.error(f"❌ Error generating OTP: {str(e)}")
                raise
            
            # ⭐ STEP 13: Create OTP verification record
            try:
                logger.info("📨 Creating OTP verification record...")
                otp_verification = OTPVerification(
                    user_id=new_user.user_id,
                    email=email,
                    otp_code=otp_code,
                    purpose='registration',
                    is_used=False,
                    expires_at=expires_at
                )
                
                db.session.add(otp_verification)
                logger.info("✅ OTP verification record created")
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Error creating OTP verification: {str(e)}")
                logger.error(traceback.format_exc())
                raise
            
            # ⭐ STEP 14: Send OTP Email
            try:
                logger.info(f"📧 Sending OTP email to {email}...")
                from app.utils.email_service import send_otp_email
                email_sent = send_otp_email(email, otp_code, 'registration')
                if email_sent:
                    logger.info("✅ OTP email sent successfully")
                else:
                    logger.warning("⚠️ OTP email not sent (email may not be configured)")
                    logger.warning("   OTP is available in backend logs for testing")
            except Exception as e:
                # Don't fail registration if email fails
                logger.error(f"⚠️ Failed to send OTP email: {str(e)}")
                logger.info("   Registration will continue - OTP available in logs")
            
            # ⭐ STEP 15: Commit everything
            try:
                logger.info("💾 Committing transaction...")
                db.session.commit()
                logger.info("✅ Transaction committed successfully")
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Database commit error: {str(e)}")
                logger.error(traceback.format_exc())
                return {'success': False, 'message': f'Database error: {str(e)}'}, 500
            
            # ⭐ SUCCESS!
            logger.info("="*60)
            logger.info(f"🎉 REGISTRATION SUCCESSFUL!")
            logger.info(f"   - User ID: {new_user.user_id}")
            logger.info(f"   - Email: {email}")
            logger.info(f"   - Username: {username}")
            logger.info(f"   - Role: {role_name}")
            logger.info(f"   - School: {school_id_number or 'None'}")
            logger.info(f"   - Department: {department_id or 'None (Admin)'}")
            logger.info("="*60)
            
            return {
                'success': True,
                'message': 'Registration successful. Please check your email for OTP.',
                'otp_code': otp_code,  # KEEP for testing, remove in production
                'email': email,
                'user_id': new_user.user_id
            }, 201
            
        except Exception as e:
            db.session.rollback()
            logger.error("="*60)
            logger.error(f"💥 CRITICAL REGISTRATION ERROR")
            logger.error("="*60)
            logger.error(f"❌ Error: {str(e)}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            logger.error(f"❌ Traceback:")
            logger.error(traceback.format_exc())
            logger.error("="*60)
            return {'success': False, 'message': 'Registration failed due to server error'}, 500
    
    @staticmethod
    def verify_otp(data):
        """Verify OTP"""
        try:
            email = data.get('email')
            otp_code = data.get('otp_code')
            purpose = data.get('purpose', 'registration')
             
            logger.info(f"🔐 Verifying OTP for {email}, purpose: {purpose}")

            # Auto-cleanup for stale registration attempts (exactly 10 minutes window).
            if purpose == 'registration':
                removed = AuthService._purge_expired_unverified_registration(email=email)
                if removed > 0:
                    return {
                        'success': False,
                        'message': 'Registration expired after 10 minutes. Please register again.'
                    }, 400
             
            # Find OTP verification
            otp_verification = OTPVerification.query.filter_by(
                email=email,
                otp_code=otp_code,
                purpose=purpose,
                is_used=False
            ).first()
            
            if not otp_verification:
                if purpose == 'registration':
                    pending_user = User.query.filter_by(email=email).first()
                    if not pending_user:
                        return {
                            'success': False,
                            'message': 'Registration record not found or already expired. Please register again.'
                        }, 400
                logger.warning(f"❌ Invalid OTP for {email}")
                return {'success': False, 'message': 'Invalid OTP'}, 400
            
            # Check if expired
            if datetime.utcnow() > otp_verification.expires_at:
                logger.warning(f"❌ Expired OTP for {email}")
                return {'success': False, 'message': 'OTP has expired'}, 400
            
            # Mark OTP as used
            otp_verification.is_used = True
            
            # Mark user as verified
            user = User.query.get(otp_verification.user_id)
            if user:
                user.is_verified = True
                logger.info(f"✅ User {email} verified successfully")
            
            db.session.commit()
            
            return {'success': True, 'message': 'Email verified successfully'}, 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ OTP verification error: {str(e)}")
            logger.error(traceback.format_exc())
            return {'success': False, 'message': 'Internal server error'}, 500
    
    @staticmethod
    def login_user(data):
        """Login user"""
        try:
            email = data.get('email')
            password = data.get('password')
            
            logger.info(f"🔐 Login attempt for: {email}")
            
            # Find user
            user = User.query.filter_by(email=email).first()
             
            if not user:
                logger.warning(f"❌ User not found: {email}")
                return {'success': False, 'message': 'Invalid email or password'}, 401

            # Auto-delete unverified registration past 10 minutes.
            if not user.is_verified and AuthService._is_registration_expired(user):
                AuthService._purge_expired_unverified_registration(user=user)
                return {
                    'success': False,
                    'message': 'Registration expired after 10 minutes. Please register again.'
                }, 403
             
            # Check password
            if not user.check_password(password):
                logger.warning(f"❌ Invalid password for: {email}")
                return {'success': False, 'message': 'Invalid email or password'}, 401
            
            # Check if verified
            if not user.is_verified:
                logger.warning(f"❌ Unverified user: {email}")
                return {'success': False, 'message': 'Please verify your email first'}, 403

            # Department approval gate for teachers (and department heads if desired)
            # Teachers should not be able to log in until the department approves them.
            if (user.role == 'teacher' or user.role_id == 2) and not user.is_approved:
                logger.warning(f"⛔ User pending department approval: {email}")
                return {
                    'success': False,
                    'message': 'Account pending department approval. Please wait for your department to approve your registration.'
                }, 403
            
            # Check if active
            if not user.is_active:
                logger.warning(f"❌ Inactive user: {email}")
                return {'success': False, 'message': 'Account is inactive'}, 403
            
            logger.info(f"✅ Login successful for: {email}")
            
            # Return user dict; tokens are generated in the route
            return {
                'success': True,
                'message': 'Login successful',
                'user': user.to_dict()
            }, 200
            
        except Exception as e:
            logger.error(f"❌ Login error: {str(e)}")
            logger.error(traceback.format_exc())
            return {'success': False, 'message': 'Internal server error'}, 500
    
    @staticmethod
    def request_otp(data):
        """Request new OTP"""
        try:
            email = data.get('email')
            purpose = data.get('purpose', 'password_reset')
             
            logger.info(f"📨 OTP request for {email}, purpose: {purpose}")

            # If this is a registration OTP request and the account is already past
            # the 10-minute verification window, remove it first.
            if purpose == 'registration':
                removed = AuthService._purge_expired_unverified_registration(email=email)
                if removed > 0:
                    return {
                        'success': False,
                        'message': 'Registration expired after 10 minutes. Please register again.'
                    }, 400
             
            # Find user
            user = User.query.filter_by(email=email).first()
            if not user:
                logger.warning(f"❌ User not found: {email}")
                if purpose == 'registration':
                    return {
                        'success': False,
                        'message': 'Registration record not found or already expired. Please register again.'
                    }, 404
                return {'success': False, 'message': 'Email not found'}, 404

            # Resend interval guard (cooldown per email+purpose).
            remaining_seconds = AuthService._otp_resend_remaining_seconds(email, purpose)
            if remaining_seconds > 0:
                wait_minutes = (remaining_seconds + 59) // 60
                return {
                    'success': False,
                    'message': (
                        f'Please wait {wait_minutes} minute(s) before requesting another OTP.'
                    ),
                    'retry_after_seconds': remaining_seconds
                }, 429
             
            # Generate new OTP
            otp_code = AuthService.generate_otp()
            expires_at = datetime.utcnow() + timedelta(
                minutes=AuthService.REGISTRATION_OTP_TTL_MINUTES
            )
            
            # Create OTP verification
            otp_verification = OTPVerification(
                user_id=user.user_id,
                email=email,
                otp_code=otp_code,
                purpose=purpose,
                is_used=False,
                expires_at=expires_at
            )
            
            db.session.add(otp_verification)
            db.session.commit()
            
            logger.info(f"✅ OTP generated for: {email}")
            
            # Send OTP via email
            try:
                logger.info(f"📧 Sending OTP email to {email}...")
                from app.utils.email_service import send_otp_email
                email_sent = send_otp_email(email, otp_code, purpose)
                if email_sent:
                    logger.info("✅ OTP email sent successfully")
                else:
                    logger.warning("⚠️ OTP email not sent (email may not be configured)")
            except Exception as email_error:
                logger.error(f"⚠️ Failed to send OTP email: {str(email_error)}")
            
            return {
                'success': True,
                'message': 'OTP sent to your email',
                'otp_code': otp_code  # KEEP for testing, remove in production
            }, 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ OTP request error: {str(e)}")
            logger.error(traceback.format_exc())
            return {'success': False, 'message': 'Internal server error'}, 500
    
    @staticmethod
    def reset_password(data):
        """Reset password with strong password validation"""
        try:
            email = data.get('email')
            otp_code = data.get('otp_code')
            new_password = data.get('new_password')
            
            logger.info(f"🔑 Password reset attempt for: {email}")
            
            # ⭐ VALIDATE STRONG PASSWORD
            is_valid, error_message = AuthService.validate_strong_password(new_password)
            if not is_valid:
                logger.error(f"❌ New password validation failed: {error_message}")
                return {'success': False, 'message': error_message}, 400
            
            logger.info("✅ New password meets strength requirements")
            
            # Verify OTP
            otp_verification = OTPVerification.query.filter_by(
                email=email,
                otp_code=otp_code,
                purpose='password_reset',
                is_used=False
            ).first()
            
            if not otp_verification:
                logger.warning(f"❌ Invalid OTP for password reset: {email}")
                return {'success': False, 'message': 'Invalid OTP'}, 400
            
            # Check if expired
            if datetime.utcnow() > otp_verification.expires_at:
                logger.warning(f"❌ Expired OTP for password reset: {email}")
                return {'success': False, 'message': 'OTP has expired'}, 400
            
            # Find user
            user = User.query.get(otp_verification.user_id)
            if not user:
                logger.error(f"❌ User not found: {email}")
                return {'success': False, 'message': 'User not found'}, 404
            
            # Update password
            user.set_password(new_password)
            
            # Mark OTP as used
            otp_verification.is_used = True
            
            db.session.commit()
            logger.info(f"✅ Password reset successful for: {email}")
            
            return {'success': True, 'message': 'Password reset successfully'}, 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Password reset error: {str(e)}")
            logger.error(traceback.format_exc())
            return {'success': False, 'message': 'Internal server error'}, 500
