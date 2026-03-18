"""
Email Service for sending OTPs and notifications

Supports multiple email providers:
- Gmail (SMTP)
- Outlook/Hotmail (SMTP)
- SendGrid (API)
- Custom SMTP server
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
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
    """Email service for sending OTPs and notifications"""
    
    def __init__(self):
        # Email configuration from environment variables
        self.smtp_server = _clean_env_value(os.environ.get('SMTP_SERVER', 'smtp.gmail.com')) or 'smtp.gmail.com'

        smtp_port_raw = _clean_env_value(os.environ.get('SMTP_PORT', '587')) or '587'
        try:
            self.smtp_port = int(smtp_port_raw)
        except (TypeError, ValueError):
            logger.warning(f"Invalid SMTP_PORT value '{smtp_port_raw}', defaulting to 587")
            self.smtp_port = 587

        self.smtp_username = _clean_env_value(os.environ.get('SMTP_USERNAME', ''))
        self.smtp_password = self._normalize_smtp_password(
            _clean_env_value(os.environ.get('SMTP_PASSWORD', ''))
        )
        self.from_email = _clean_env_value(os.environ.get('FROM_EMAIL', self.smtp_username)) or self.smtp_username
        self.from_name = _clean_env_value(os.environ.get('FROM_NAME', 'AWEGen System')) or 'AWEGen System'
        
        # Email enabled flag
        self.email_enabled = bool(self.smtp_username and self.smtp_password)
        
        if not self.email_enabled:
            logger.warning("Email not configured - OTPs will only be logged")

    def _normalize_smtp_password(self, password):
        """Normalize Gmail app passwords copied with visual separator spaces."""
        if not password:
            return ''

        if 'gmail' in self.smtp_server.lower():
            return ''.join(password.split())

        return password
    
    def send_email(self, to_email, subject, body_html, body_text=None):
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text email body (optional)
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.email_enabled:
            logger.info(f"Email disabled - Would send to {to_email}: {subject}")
            logger.info(f"Body: {body_text or body_html}")
            return False
        
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = f"{self.from_name} <{self.from_email}>"
            message['To'] = to_email
            
            # Add text and HTML parts
            if body_text:
                part1 = MIMEText(body_text, 'plain')
                message.attach(part1)
            
            part2 = MIMEText(body_html, 'html')
            message.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
            
            logger.info(f"✅ Email sent successfully to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ Failed to send email to {to_email}: {str(e)}")
            logger.error(
                "SMTP authentication failed. Check SMTP_USERNAME/SMTP_PASSWORD. "
                "If using Gmail, use a valid 16-character App Password."
            )
            return False
        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_otp_email(self, to_email, otp_code, purpose='registration'):
        """
        Send OTP email
        
        Args:
            to_email: Recipient email address
            otp_code: 6-digit OTP code
            purpose: Purpose of OTP (registration, password_reset, etc.)
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Email subject based on purpose
        subjects = {
            'registration': 'Verify Your Account - AWEGen',
            'password_reset': 'Reset Your Password - AWEGen',
            'email_verification': 'Verify Your Email - AWEGen'
        }
        subject = subjects.get(purpose, 'Your OTP Code - AWEGen')
        
        # Email body
        body_html = self._get_otp_email_html(otp_code, purpose)
        body_text = self._get_otp_email_text(otp_code, purpose)
        
        # Log OTP for development (remove in production)
        logger.info(f"📧 Sending OTP to {to_email}: {otp_code}")
        
        return self.send_email(to_email, subject, body_html, body_text)

    def send_account_approval_email(self, to_email, full_name=None, role_name='teacher'):
        """
        Send account approval notification email.

        Args:
            to_email: Recipient email address
            full_name: User full name
            role_name: User role label

        Returns:
            bool: True if sent successfully, False otherwise
        """
        subject = 'Your AWEGen account has been approved'
        body_html = self._get_account_approval_email_html(full_name, role_name)
        body_text = self._get_account_approval_email_text(full_name, role_name)

        logger.info(f"Sending account approval email to {to_email}")
        return self.send_email(to_email, subject, body_html, body_text)
    
    def _get_otp_email_html(self, otp_code, purpose):
        """Generate HTML email body for OTP"""
        purpose_text = {
            'registration': 'complete your registration',
            'password_reset': 'reset your password',
            'email_verification': 'verify your email'
        }.get(purpose, 'verify your account')
        
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
                    <strong>⚠️ Security Notice:</strong><br>
                    • Never share this code with anyone<br>
                    • AWEGen staff will never ask for your OTP<br>
                    • This code expires in 10 minutes
                </div>
                
                <p style="margin-top: 20px;">If you didn't request this code, please ignore this email or contact support if you're concerned about your account security.</p>
                
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
        """Generate plain text email body for OTP"""
        purpose_text = {
            'registration': 'complete your registration',
            'password_reset': 'reset your password',
            'email_verification': 'verify your email'
        }.get(purpose, 'verify your account')
        
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

If you didn't request this code, please ignore this email or contact support.

---
This is an automated message from AWEGen.
© 2026 AWEGen - AI-Assisted Written Exam Generator
        """


    def _get_account_approval_email_html(self, full_name=None, role_name='teacher'):
        """Generate HTML email body for account approval notification."""
        safe_name = (full_name or '').strip() or 'User'
        safe_role = (role_name or 'teacher').replace('_', ' ').title()
        login_url = (os.environ.get('APP_LOGIN_URL', '') or '').strip()
        login_line = (
            f'<p style="margin: 16px 0;">You can now sign in here: '
            f'<a href="{login_url}" style="color:#EAB308;font-weight:600;">{login_url}</a></p>'
            if login_url else ''
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

    def _get_account_approval_email_text(self, full_name=None, role_name='teacher'):
        """Generate plain text email body for account approval notification."""
        safe_name = (full_name or '').strip() or 'User'
        safe_role = (role_name or 'teacher').replace('_', ' ').title()
        login_url = (os.environ.get('APP_LOGIN_URL', '') or '').strip()
        login_line = f'Login URL: {login_url}\\n\\n' if login_url else ''

        return f"""
AWEGen - Account Approved

Hello {safe_name},

Your {safe_role} account in AWEGen has been approved.
You can now access the system using your registered email and password.

{login_line}If you did not request this account, please contact your administrator.

---
This is an automated message from AWEGen.
© 2026 AWEGen - AI-Assisted Written Exam Generator
        """


# Create global email service instance
email_service = EmailService()


def send_otp_email(to_email, otp_code, purpose='registration'):
    """
    Convenience function to send OTP email
    
    Args:
        to_email: Recipient email address
        otp_code: 6-digit OTP code
        purpose: Purpose of OTP
    
    Returns:
        bool: True if sent successfully
    """
    return email_service.send_otp_email(to_email, otp_code, purpose)


def send_account_approval_email(to_email, full_name=None, role_name='teacher'):
    """
    Convenience function to send account approval notification email.

    Args:
        to_email: Recipient email address
        full_name: User full name
        role_name: User role label

    Returns:
        bool: True if sent successfully
    """
    return email_service.send_account_approval_email(
        to_email=to_email,
        full_name=full_name,
        role_name=role_name
    )
