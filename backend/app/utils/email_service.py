
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _clean_env_value(value):
    """Trim whitespace and surrounding quotes from env values."""
    if value is None:
        return ""

    cleaned = str(value).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


class EmailService:
    """Email service for sending OTPs and notifications."""

    def __init__(self):
        self.smtp_server = _clean_env_value(os.environ.get("SMTP_SERVER", "smtp.gmail.com")) or "smtp.gmail.com"

        smtp_port_raw = _clean_env_value(os.environ.get("SMTP_PORT", "587")) or "587"
        try:
            self.smtp_port = int(smtp_port_raw)
        except (TypeError, ValueError):
            logger.warning(f"Invalid SMTP_PORT value '{smtp_port_raw}', defaulting to 587")
            self.smtp_port = 587

        self.smtp_username = _clean_env_value(os.environ.get("SMTP_USERNAME", ""))
        self.smtp_password = self._normalize_smtp_password(
            _clean_env_value(os.environ.get("SMTP_PASSWORD", ""))
        )
        self.from_email = _clean_env_value(os.environ.get("FROM_EMAIL", self.smtp_username)) or self.smtp_username
        self.from_name = _clean_env_value(os.environ.get("FROM_NAME", "AWEGen System")) or "AWEGen System"

        self.email_enabled = bool(self.smtp_username and self.smtp_password)
        if not self.email_enabled:
            logger.warning("Email not configured - OTPs and notifications will only be logged")

    def _normalize_smtp_password(self, password):
        """Normalize Gmail app passwords copied with visual separator spaces."""
        if not password:
            return ""

        if "gmail" in self.smtp_server.lower():
            return "".join(password.split())

        return password

    def send_email(self, to_email, subject, body_html, body_text=None):
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text email body

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.email_enabled:
            logger.info(f"Email disabled - Would send to {to_email}: {subject}")
            logger.info(f"Body: {body_text or body_html}")
            return False

        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email

            if body_text:
                message.attach(MIMEText(body_text, "plain"))

            message.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)

            logger.info(f"Email sent successfully to {to_email}")
            return True
        except smtplib.SMTPAuthenticationError as exc:
            logger.error(f"Failed to send email to {to_email}: {exc}")
            logger.error(
                "SMTP authentication failed. Check SMTP_USERNAME/SMTP_PASSWORD. "
                "If using Gmail, use a valid 16-character App Password."
            )
            return False
        except Exception as exc:
            logger.error(f"Failed to send email to {to_email}: {exc}")
            return False

    def send_otp_email(self, to_email, otp_code, purpose="registration"):
        """Send OTP email."""
        subjects = {
            "registration": "Verify Your Account - AWEGen",
            "password_reset": "Reset Your Password - AWEGen",
            "email_verification": "Verify Your Email - AWEGen",
        }
        subject = subjects.get(purpose, "Your OTP Code - AWEGen")
        body_html = self._get_otp_email_html(otp_code, purpose)
        body_text = self._get_otp_email_text(otp_code, purpose)

        logger.info(f"Sending OTP to {to_email}: {otp_code}")
        return self.send_email(to_email, subject, body_html, body_text)

    def send_account_approval_email(self, to_email, full_name=None, role_name="teacher"):
        """Send account approval notification email."""
        subject = "Your AWEGen account has been approved"
        body_html = self._get_account_approval_email_html(full_name, role_name)
        body_text = self._get_account_approval_email_text(full_name, role_name)

        logger.info(f"Sending account approval email to {to_email}")
        return self.send_email(to_email, subject, body_html, body_text)

    def send_account_created_email(
        self,
        to_email,
        full_name=None,
        role_name="teacher",
        department_name=None,
        is_active=True,
        is_approved=True,
    ):
        """Send account created notification email."""
        subject = "Welcome to AWEGen"
        body_html = self._get_account_created_email_html(
            full_name=full_name,
            role_name=role_name,
            department_name=department_name,
            is_active=is_active,
            is_approved=is_approved,
        )
        body_text = self._get_account_created_email_text(
            full_name=full_name,
            role_name=role_name,
            department_name=department_name,
            is_active=is_active,
            is_approved=is_approved,
        )

        logger.info(f"Sending account created email to {to_email}")
        return self.send_email(to_email, subject, body_html, body_text)

    def send_email_change_confirmation_email(self, to_email, full_name=None, role_name="teacher"):
        """Send email change confirmation notification."""
        subject = "Your AWEGen email was updated"
        body_html = self._get_email_change_confirmation_email_html(full_name, role_name, to_email)
        body_text = self._get_email_change_confirmation_email_text(full_name, role_name, to_email)

        logger.info(f"Sending email change confirmation to {to_email}")
        return self.send_email(to_email, subject, body_html, body_text)

    def send_exam_decision_email(
        self,
        to_email,
        full_name=None,
        exam_title=None,
        decision_status="approved",
        feedback=None,
        reviewer_label="admin",
    ):
        """Send exam review decision notification email."""
        normalized_status = str(decision_status or "").strip().lower()
        subject_map = {
            "approved": "Your exam was approved - AWEGen",
            "revision_required": "Your exam needs revision - AWEGen",
            "rejected": "Your exam was rejected - AWEGen",
        }
        subject = subject_map.get(normalized_status, "Your exam has a review update - AWEGen")
        body_html = self._get_exam_decision_email_html(
            full_name=full_name,
            exam_title=exam_title,
            decision_status=normalized_status,
            feedback=feedback,
            reviewer_label=reviewer_label,
        )
        body_text = self._get_exam_decision_email_text(
            full_name=full_name,
            exam_title=exam_title,
            decision_status=normalized_status,
            feedback=feedback,
            reviewer_label=reviewer_label,
        )

        logger.info(f"Sending exam decision email to {to_email} for status {normalized_status}")
        return self.send_email(to_email, subject, body_html, body_text)

    def send_exam_submission_email(
        self,
        to_email,
        full_name=None,
        sender_name=None,
        exam_title=None,
        department_name=None,
        action_label="submitted",
        notes=None,
    ):
        """Send department email when an exam is submitted for review."""
        subject = "New exam pending department review - AWEGen"
        body_html = self._get_exam_submission_email_html(
            full_name=full_name,
            sender_name=sender_name,
            exam_title=exam_title,
            department_name=department_name,
            action_label=action_label,
            notes=notes,
        )
        body_text = self._get_exam_submission_email_text(
            full_name=full_name,
            sender_name=sender_name,
            exam_title=exam_title,
            department_name=department_name,
            action_label=action_label,
            notes=notes,
        )

        logger.info(f"Sending exam submission email to {to_email} for exam {exam_title}")
        return self.send_email(to_email, subject, body_html, body_text)

    def send_exam_follow_up_email(
        self,
        to_email,
        full_name=None,
        category_name=None,
        department_name=None,
        teacher_status=None,
        exam_title=None,
    ):
        """Send a reminder email for incomplete exam requirements."""
        safe_category = (category_name or "selected term").strip()
        subject = f"Exam follow-up for {safe_category} - AWEGen"
        body_html = self._get_exam_follow_up_email_html(
            full_name=full_name,
            category_name=safe_category,
            department_name=department_name,
            teacher_status=teacher_status,
            exam_title=exam_title,
        )
        body_text = self._get_exam_follow_up_email_text(
            full_name=full_name,
            category_name=safe_category,
            department_name=department_name,
            teacher_status=teacher_status,
            exam_title=exam_title,
        )

        logger.info(f"Sending exam follow-up email to {to_email} for category {safe_category}")
        return self.send_email(to_email, subject, body_html, body_text)

    def _get_login_line_html(self, label_text):
        login_url = (os.environ.get("APP_LOGIN_URL", "") or "").strip()
        if not login_url:
            return ""

        return (
            f'<p style="margin: 16px 0;">{label_text} '
            f'<a href="{login_url}" style="color:#EAB308;font-weight:600;">{login_url}</a></p>'
        )

    def _get_login_line_text(self):
        login_url = (os.environ.get("APP_LOGIN_URL", "") or "").strip()
        return f"Login URL: {login_url}\n\n" if login_url else ""

    def _get_otp_email_html(self, otp_code, purpose):
        """Generate HTML email body for OTP."""
        purpose_text = {
            "registration": "complete your registration",
            "password_reset": "reset your password",
            "email_verification": "verify your email",
        }.get(purpose, "verify your account")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #f9f9f9;
                    border-radius: 10px;
                    padding: 30px;
                    border: 1px solid #ddd;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .logo {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #EAB308;
                    margin-bottom: 10px;
                }}
                .otp-code {{
                    background-color: #fff;
                    border: 2px dashed #EAB308;
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                    margin: 30px 0;
                }}
                .otp-number {{
                    font-size: 36px;
                    font-weight: bold;
                    color: #EAB308;
                    letter-spacing: 8px;
                    font-family: 'Courier New', monospace;
                }}
                .warning {{
                    background-color: #fff3cd;
                    border: 1px solid #ffc107;
                    border-radius: 5px;
                    padding: 15px;
                    margin-top: 20px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">AWEGen</div>
                    <h2 style="color: #333; margin: 0;">Verification Code</h2>
                </div>

                <p>Hello!</p>

                <p>You requested to <strong>{purpose_text}</strong> on AWEGen. Please use the following One-Time Password (OTP) to continue:</p>

                <div class="otp-code">
                    <div style="color: #666; font-size: 14px; margin-bottom: 10px;">Your OTP Code:</div>
                    <div class="otp-number">{otp_code}</div>
                    <div style="color: #666; font-size: 12px; margin-top: 10px;">Valid for 10 minutes</div>
                </div>

                <p>Enter this code on the verification page to proceed.</p>

                <div class="warning">
                    <strong>Security Notice:</strong><br>
                    - Never share this code with anyone<br>
                    - AWEGen staff will never ask for your OTP<br>
                    - This code expires in 10 minutes
                </div>

                <p style="margin-top: 20px;">If you did not request this code, please ignore this email or contact support if you are concerned about your account security.</p>

                <div class="footer">
                    <p>This is an automated message from AWEGen.<br>
                    Please do not reply to this email.</p>
                    <p>&copy; 2026 AWEGen - AI-Assisted Written Exam Generator</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_otp_email_text(self, otp_code, purpose):
        """Generate plain text email body for OTP."""
        purpose_text = {
            "registration": "complete your registration",
            "password_reset": "reset your password",
            "email_verification": "verify your email",
        }.get(purpose, "verify your account")

        return f"""
AWEGen - Verification Code

Hello!

You requested to {purpose_text} on AWEGen.

Your One-Time Password (OTP) is: {otp_code}

This code is valid for 10 minutes.

Enter this code on the verification page to proceed.

SECURITY NOTICE:
- Never share this code with anyone
- AWEGen staff will never ask for your OTP
- This code expires in 10 minutes

If you did not request this code, please ignore this email or contact support.

---
This is an automated message from AWEGen.
Copyright 2026 AWEGen - AI-Assisted Written Exam Generator
        """

    def _get_account_approval_email_html(self, full_name=None, role_name="teacher"):
        """Generate HTML email body for account approval notification."""
        safe_name = (full_name or "").strip() or "User"
        safe_role = (role_name or "teacher").replace("_", " ").title()
        login_line = self._get_login_line_html("You can now sign in here:")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #f9f9f9;
                    border-radius: 10px;
                    padding: 30px;
                    border: 1px solid #ddd;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 24px;
                }}
                .logo {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #EAB308;
                    margin-bottom: 10px;
                }}
                .status {{
                    background-color: #ecfdf5;
                    border: 1px solid #10b981;
                    color: #065f46;
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">AWEGen</div>
                    <h2 style="color: #333; margin: 0;">Account Approved</h2>
                </div>

                <p>Hello {safe_name},</p>
                <p>Your <strong>{safe_role}</strong> account in AWEGen has been approved.</p>

                <div class="status">
                    You can now access the system using your registered email and password.
                </div>

                {login_line}

                <p>If you did not request this account, please contact your administrator.</p>

                <div class="footer">
                    <p>This is an automated message from AWEGen.<br>
                    Please do not reply to this email.</p>
                    <p>&copy; 2026 AWEGen - AI-Assisted Written Exam Generator</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_account_approval_email_text(self, full_name=None, role_name="teacher"):
        """Generate plain text email body for account approval notification."""
        safe_name = (full_name or "").strip() or "User"
        safe_role = (role_name or "teacher").replace("_", " ").title()
        login_line = self._get_login_line_text()

        return f"""
AWEGen - Account Approved

Hello {safe_name},

Your {safe_role} account in AWEGen has been approved.
You can now access the system using your registered email and password.

{login_line}If you did not request this account, please contact your administrator.

---
This is an automated message from AWEGen.
Copyright 2026 AWEGen - AI-Assisted Written Exam Generator
        """

    def _get_account_created_email_html(
        self,
        full_name=None,
        role_name="teacher",
        department_name=None,
        is_active=True,
        is_approved=True,
    ):
        """Generate HTML email body for account creation notification."""
        safe_name = (full_name or "").strip() or "User"
        safe_role = (role_name or "teacher").replace("_", " ").title()
        safe_department = (department_name or "").strip()

        if not is_active:
            status_title = "Welcome to AWEGen"
            status_class = "background-color: #f8fafc; border: 1px solid #94a3b8; color: #334155;"
            status_message = "Welcome to AWEGen. Your account has been created, but it is currently inactive."
            next_step = (
                "Your administrator needs to activate your account before you can sign in."
            )
            login_line = self._get_login_line_html("Once activated, you can sign in here:")
        elif not is_approved:
            status_title = "Welcome to AWEGen"
            status_class = "background-color: #fffbeb; border: 1px solid #f59e0b; color: #92400e;"
            status_message = "Welcome to AWEGen. Your account has been created and is waiting for department approval."
            next_step = (
                "You will be able to sign in after the selected department approves your account."
            )
            login_line = self._get_login_line_html("After approval, you can sign in here:")
        else:
            status_title = "Welcome to AWEGen"
            status_class = "background-color: #ecfdf5; border: 1px solid #10b981; color: #065f46;"
            status_message = "Welcome to AWEGen. Your account has been created and is ready to use."
            next_step = (
                "You can now sign in using your registered email and the password provided by your administrator."
            )
            login_line = self._get_login_line_html("You can sign in here:")

        department_block = (
            f"""
                <div style="background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; margin: 16px 0;">
                    <strong>Department:</strong> {safe_department}
                </div>
            """
            if safe_department
            else ""
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #f9f9f9;
                    border-radius: 10px;
                    padding: 30px;
                    border: 1px solid #ddd;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 24px;
                }}
                .logo {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #EAB308;
                    margin-bottom: 10px;
                }}
                .status {{
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">AWEGen</div>
                    <h2 style="color: #333; margin: 0;">{status_title}</h2>
                </div>

                <p>Hello {safe_name},</p>
                <p>Welcome!</p>
                <p>Your <strong>{safe_role}</strong> account in AWEGen has been created by the administrator.</p>

                {department_block}

                <div class="status" style="{status_class}">
                    {status_message}
                </div>

                <p>{next_step}</p>

                {login_line}

                <p>If you were not expecting this account, please contact your administrator.</p>

                <div class="footer">
                    <p>This is an automated message from AWEGen.<br>
                    Please do not reply to this email.</p>
                    <p>&copy; 2026 AWEGen - AI-Assisted Written Exam Generator</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_account_created_email_text(
        self,
        full_name=None,
        role_name="teacher",
        department_name=None,
        is_active=True,
        is_approved=True,
    ):
        """Generate plain text email body for account creation notification."""
        safe_name = (full_name or "").strip() or "User"
        safe_role = (role_name or "teacher").replace("_", " ").title()
        safe_department = (department_name or "").strip()

        if not is_active:
            status_message = "Welcome to AWEGen. Your account has been created, but it is currently inactive."
            next_step = "Your administrator needs to activate your account before you can sign in."
            login_line = "Once activated, " + self._get_login_line_text().lower()
        elif not is_approved:
            status_message = "Welcome to AWEGen. Your account has been created and is waiting for department approval."
            next_step = "You will be able to sign in after the selected department approves your account."
            login_line = "After approval, " + self._get_login_line_text().lower()
        else:
            status_message = "Welcome to AWEGen. Your account has been created and is ready to use."
            next_step = (
                "You can now sign in using your registered email and the password provided by your administrator."
            )
            login_line = self._get_login_line_text()

        department_line = f"Department: {safe_department}\n\n" if safe_department else ""

        return f"""
AWEGen - Welcome

Hello {safe_name},

Welcome!

Your {safe_role} account in AWEGen has been created by the administrator.

{department_line}{status_message}
{next_step}

{login_line}If you were not expecting this account, please contact your administrator.

---
This is an automated message from AWEGen.
Copyright 2026 AWEGen - AI-Assisted Written Exam Generator
        """

    def _get_email_change_confirmation_email_html(self, full_name=None, role_name="teacher", new_email=""):
        """Generate HTML email body for email change confirmation."""
        safe_name = (full_name or "").strip() or "User"
        safe_role = (role_name or "teacher").replace("_", " ").title()
        safe_email = (new_email or "").strip()
        login_line = self._get_login_line_html("You can continue using your account here:")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #f9f9f9;
                    border-radius: 10px;
                    padding: 30px;
                    border: 1px solid #ddd;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 24px;
                }}
                .logo {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #EAB308;
                    margin-bottom: 10px;
                }}
                .status {{
                    background-color: #ecfeff;
                    border: 1px solid #06b6d4;
                    color: #155e75;
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">AWEGen</div>
                    <h2 style="color: #333; margin: 0;">Email Updated</h2>
                </div>

                <p>Hello {safe_name},</p>
                <p>Your <strong>{safe_role}</strong> account email in AWEGen was updated successfully.</p>

                <div class="status">
                    Your new sign-in email is <strong>{safe_email}</strong>.
                </div>

                {login_line}

                <p>If you did not make this change, please reset your password immediately and contact your administrator.</p>

                <div class="footer">
                    <p>This is an automated message from AWEGen.<br>
                    Please do not reply to this email.</p>
                    <p>&copy; 2026 AWEGen - AI-Assisted Written Exam Generator</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_email_change_confirmation_email_text(self, full_name=None, role_name="teacher", new_email=""):
        """Generate plain text email body for email change confirmation."""
        safe_name = (full_name or "").strip() or "User"
        safe_role = (role_name or "teacher").replace("_", " ").title()
        safe_email = (new_email or "").strip()
        login_line = self._get_login_line_text()

        return f"""
AWEGen - Email Updated

Hello {safe_name},

Your {safe_role} account email in AWEGen was updated successfully.
Your new sign-in email is: {safe_email}

{login_line}If you did not make this change, please reset your password immediately and contact your administrator.

---
This is an automated message from AWEGen.
Copyright 2026 AWEGen - AI-Assisted Written Exam Generator
        """

    def _get_exam_decision_label(self, decision_status):
        normalized_status = str(decision_status or "").strip().lower()
        status_map = {
            "approved": ("Approved", "#065f46", "#ecfdf5", "#10b981"),
            "revision_required": ("Revision Required", "#9a3412", "#fff7ed", "#f97316"),
            "rejected": ("Rejected", "#991b1b", "#fef2f2", "#ef4444"),
        }
        return status_map.get(normalized_status, ("Review Update", "#1f2937", "#f3f4f6", "#9ca3af"))

    def _get_exam_decision_intro(self, exam_title, decision_status, reviewer_label):
        safe_title = (exam_title or "Untitled Exam").strip()
        reviewer = (reviewer_label or "admin").strip()
        normalized_status = str(decision_status or "").strip().lower()

        if normalized_status == "approved":
            return f'Your exam "{safe_title}" was approved by the {reviewer}.'
        if normalized_status == "revision_required":
            return f'Your exam "{safe_title}" needs revision based on {reviewer} review.'
        if normalized_status == "rejected":
            return f'Your exam "{safe_title}" was rejected by the {reviewer}.'
        return f'Your exam "{safe_title}" has a new review update from the {reviewer}.'

    def _get_exam_submission_intro(self, sender_name, exam_title, department_name, action_label):
        safe_sender = (sender_name or "A teacher").strip() or "A teacher"
        safe_title = (exam_title or "Untitled Exam").strip()
        safe_department = (department_name or "your department").strip() or "your department"
        normalized_action = str(action_label or "").strip().lower()

        if normalized_action == "sent":
            return f'{safe_sender} sent the exam "{safe_title}" to {safe_department} for review.'
        return f'{safe_sender} submitted the exam "{safe_title}" to {safe_department} for review.'

    def _get_exam_submission_email_html(
        self,
        full_name=None,
        sender_name=None,
        exam_title=None,
        department_name=None,
        action_label="submitted",
        notes=None,
    ):
        """Generate HTML email body for department exam submission notifications."""
        safe_name = (full_name or "").strip() or "Reviewer"
        safe_title = (exam_title or "Untitled Exam").strip()
        safe_department = (department_name or "your department").strip() or "your department"
        intro_text = self._get_exam_submission_intro(sender_name, safe_title, safe_department, action_label)
        note_text = (notes or "").strip()
        login_line = self._get_login_line_html("Open AWEGen here:")
        notes_block = (
            f"""
                <div class="notes">
                    <div class="notes-title">Submission Notes</div>
                    <div>{note_text}</div>
                </div>
            """
            if note_text
            else ""
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #f9f9f9;
                    border-radius: 10px;
                    padding: 30px;
                    border: 1px solid #ddd;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 24px;
                }}
                .logo {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #EAB308;
                    margin-bottom: 10px;
                }}
                .status {{
                    background-color: #eff6ff;
                    border: 1px solid #60a5fa;
                    color: #1d4ed8;
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                    font-weight: 600;
                }}
                .details {{
                    background-color: #ffffff;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                }}
                .details-title {{
                    font-weight: 700;
                    margin-bottom: 8px;
                }}
                .notes {{
                    background-color: #ffffff;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                }}
                .notes-title {{
                    font-weight: 700;
                    margin-bottom: 8px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">AWEGen</div>
                    <h2 style="color: #333; margin: 0;">Exam Submission Notification</h2>
                </div>

                <p>Hello {safe_name},</p>
                <p>{intro_text}</p>

                <div class="status">
                    Status: Pending Department Review
                </div>

                <div class="details">
                    <div class="details-title">Exam Details</div>
                    <div><strong>Exam Title:</strong> {safe_title}</div>
                    <div><strong>Department:</strong> {safe_department}</div>
                </div>

                {notes_block}

                <p>Please open AWEGen to review the submitted exam.</p>

                {login_line}

                <div class="footer">
                    <p>This is an automated message from AWEGen.<br>
                    Please do not reply to this email.</p>
                    <p>&copy; 2026 AWEGen - AI-Assisted Written Exam Generator</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_exam_submission_email_text(
        self,
        full_name=None,
        sender_name=None,
        exam_title=None,
        department_name=None,
        action_label="submitted",
        notes=None,
    ):
        """Generate plain text email body for department exam submission notifications."""
        safe_name = (full_name or "").strip() or "Reviewer"
        safe_title = (exam_title or "Untitled Exam").strip()
        safe_department = (department_name or "your department").strip() or "your department"
        intro_text = self._get_exam_submission_intro(sender_name, safe_title, safe_department, action_label)
        note_text = (notes or "").strip()
        login_line = self._get_login_line_text()
        notes_block = f"\nSubmission Notes:\n{note_text}\n" if note_text else "\n"

        return f"""
AWEGen - Exam Submission Notification

Hello {safe_name},

{intro_text}

Status: Pending Department Review
Exam Title: {safe_title}
Department: {safe_department}
{notes_block}
Please open AWEGen to review the submitted exam.

{login_line}This is an automated message from AWEGen.
Copyright 2026 AWEGen - AI-Assisted Written Exam Generator
        """

    def _get_exam_decision_email_html(
        self,
        full_name=None,
        exam_title=None,
        decision_status="approved",
        feedback=None,
        reviewer_label="admin",
    ):
        """Generate HTML email body for exam review decisions."""
        safe_name = (full_name or "").strip() or "User"
        safe_title = (exam_title or "Untitled Exam").strip()
        status_label, text_color, background_color, border_color = self._get_exam_decision_label(decision_status)
        intro_text = self._get_exam_decision_intro(safe_title, decision_status, reviewer_label)
        feedback_text = (feedback or "").strip()
        login_line = self._get_login_line_html("Open AWEGen here:")
        feedback_block = (
            f"""
                <div class="feedback">
                    <div class="feedback-title">Reviewer Feedback</div>
                    <div>{feedback_text}</div>
                </div>
            """
            if feedback_text
            else ""
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #f9f9f9;
                    border-radius: 10px;
                    padding: 30px;
                    border: 1px solid #ddd;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 24px;
                }}
                .logo {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #EAB308;
                    margin-bottom: 10px;
                }}
                .status {{
                    background-color: {background_color};
                    border: 1px solid {border_color};
                    color: {text_color};
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                    font-weight: 600;
                }}
                .feedback {{
                    background-color: #ffffff;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                }}
                .feedback-title {{
                    font-weight: 700;
                    margin-bottom: 8px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">AWEGen</div>
                    <h2 style="color: #333; margin: 0;">Exam Review Update</h2>
                </div>

                <p>Hello {safe_name},</p>
                <p>{intro_text}</p>

                <div class="status">
                    Status: {status_label}
                </div>

                <p><strong>Exam Title:</strong> {safe_title}</p>

                {feedback_block}

                {login_line}

                <div class="footer">
                    <p>This is an automated message from AWEGen.<br>
                    Please do not reply to this email.</p>
                    <p>&copy; 2026 AWEGen - AI-Assisted Written Exam Generator</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_exam_decision_email_text(
        self,
        full_name=None,
        exam_title=None,
        decision_status="approved",
        feedback=None,
        reviewer_label="admin",
    ):
        """Generate plain text email body for exam review decisions."""
        safe_name = (full_name or "").strip() or "User"
        safe_title = (exam_title or "Untitled Exam").strip()
        status_label, _, _, _ = self._get_exam_decision_label(decision_status)
        intro_text = self._get_exam_decision_intro(safe_title, decision_status, reviewer_label)
        feedback_text = (feedback or "").strip()
        login_line = self._get_login_line_text()
        feedback_block = f"\nReviewer Feedback:\n{feedback_text}\n" if feedback_text else "\n"

        return f"""
AWEGen - Exam Review Update

Hello {safe_name},

{intro_text}

Status: {status_label}
Exam Title: {safe_title}
{feedback_block}
{login_line}This is an automated message from AWEGen.
Copyright 2026 AWEGen - AI-Assisted Written Exam Generator
        """

    def _get_exam_follow_up_email_html(
        self,
        full_name=None,
        category_name=None,
        department_name=None,
        teacher_status=None,
        exam_title=None,
    ):
        safe_name = (full_name or "").strip() or "User"
        safe_category = (category_name or "selected term").strip()
        safe_department = (department_name or "your department").strip()
        normalized_status = str(teacher_status or '').strip().lower()
        safe_exam_title = (exam_title or '').strip()
        summary_text = (
            'You still need to create your required exam for this term.'
            if normalized_status == 'missing'
            else 'Your exam for this term already exists, but it still needs follow-up.'
        )
        exam_block = (
            f"""
                <div class="subjects">
                    <div class="subjects-title">Current Exam</div>
                    <div>{safe_exam_title}</div>
                </div>
            """
            if safe_exam_title
            else ''
        )
        login_line = self._get_login_line_html("Open AWEGen here:")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #f9f9f9;
                    border-radius: 10px;
                    padding: 30px;
                    border: 1px solid #ddd;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 24px;
                }}
                .logo {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #EAB308;
                    margin-bottom: 10px;
                }}
                .summary {{
                    background-color: #fffbeb;
                    border: 1px solid #fcd34d;
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                }}
                .subjects {{
                    background-color: #ffffff;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 14px;
                    margin: 20px 0;
                }}
                .subjects-title {{
                    font-weight: 700;
                    margin-bottom: 8px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">AWEGen</div>
                    <h2 style="color: #333; margin: 0;">Exam Follow-up Reminder</h2>
                </div>

                <p>Hello {safe_name},</p>
                <p>
                    This is a reminder from {safe_department} that your
                    <strong>{safe_category}</strong> exam requirements are not complete yet.
                </p>

                <div class="summary">
                    {summary_text}
                </div>

                {exam_block}

                <p>Please prepare and submit the remaining exam requirements as soon as possible.</p>

                {login_line}

                <div class="footer">
                    <p>This is an automated message from AWEGen.<br>
                    Please do not reply to this email.</p>
                    <p>&copy; 2026 AWEGen - AI-Assisted Written Exam Generator</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_exam_follow_up_email_text(
        self,
        full_name=None,
        category_name=None,
        department_name=None,
        teacher_status=None,
        exam_title=None,
    ):
        safe_name = (full_name or "").strip() or "User"
        safe_category = (category_name or "selected term").strip()
        safe_department = (department_name or "your department").strip()
        normalized_status = str(teacher_status or '').strip().lower()
        safe_exam_title = (exam_title or '').strip()
        summary_text = (
            'You still need to create your required exam for this term.'
            if normalized_status == 'missing'
            else 'Your exam for this term already exists, but it still needs follow-up.'
        )
        login_line = self._get_login_line_text()

        return f"""
AWEGen - Exam Follow-up Reminder

Hello {safe_name},

This is a reminder from {safe_department} that your {safe_category} exam requirements are not complete yet.

{summary_text}

Current Exam:
{safe_exam_title or '- No exam created yet.'}

Please prepare and submit the remaining exam requirements as soon as possible.

{login_line}This is an automated message from AWEGen.
Copyright 2026 AWEGen - AI-Assisted Written Exam Generator
        """


email_service = EmailService()


def send_otp_email(to_email, otp_code, purpose="registration"):
    """Convenience function to send OTP email."""
    return email_service.send_otp_email(to_email, otp_code, purpose)


def send_account_approval_email(to_email, full_name=None, role_name="teacher"):
    """Convenience function to send account approval notification email."""
    return email_service.send_account_approval_email(
        to_email=to_email,
        full_name=full_name,
        role_name=role_name,
    )


def send_account_created_email(
    to_email,
    full_name=None,
    role_name="teacher",
    department_name=None,
    is_active=True,
    is_approved=True,
):
    """Convenience function to send account created notification email."""
    return email_service.send_account_created_email(
        to_email=to_email,
        full_name=full_name,
        role_name=role_name,
        department_name=department_name,
        is_active=is_active,
        is_approved=is_approved,
    )


def send_email_change_confirmation_email(to_email, full_name=None, role_name="teacher"):
    """Convenience function to send email change confirmation notification."""
    return email_service.send_email_change_confirmation_email(
        to_email=to_email,
        full_name=full_name,
        role_name=role_name,
    )


def send_exam_decision_email(
    to_email,
    full_name=None,
    exam_title=None,
    decision_status="approved",
    feedback=None,
    reviewer_label="admin",
):
    """Convenience function to send exam review decision notification email."""
    return email_service.send_exam_decision_email(
        to_email=to_email,
        full_name=full_name,
        exam_title=exam_title,
        decision_status=decision_status,
        feedback=feedback,
        reviewer_label=reviewer_label,
    )


def send_exam_submission_email(
    to_email,
    full_name=None,
    sender_name=None,
    exam_title=None,
    department_name=None,
    action_label="submitted",
    notes=None,
):
    """Convenience function to send department exam submission notification email."""
    return email_service.send_exam_submission_email(
        to_email=to_email,
        full_name=full_name,
        sender_name=sender_name,
        exam_title=exam_title,
        department_name=department_name,
        action_label=action_label,
        notes=notes,
    )


def send_exam_follow_up_email(
    to_email,
    full_name=None,
    category_name=None,
    department_name=None,
    teacher_status=None,
    exam_title=None,
):
    """Convenience function to send exam follow-up reminder email."""
    return email_service.send_exam_follow_up_email(
        to_email=to_email,
        full_name=full_name,
        category_name=category_name,
        department_name=department_name,
        teacher_status=teacher_status,
        exam_title=exam_title,
    )
