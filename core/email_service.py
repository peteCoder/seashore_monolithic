"""
Email Service for Seashore Microfinance
========================================

Handles all email sending functionality using SMTP
"""

import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def generate_verification_code():
    """Generate a random 6-digit verification code"""
    return str(random.randint(100000, 999999))


def send_email(to_email, subject, html_content):
    """
    Send HTML email using SMTP
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Email configuration from settings
        smtp_host = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
        smtp_port = getattr(settings, 'EMAIL_PORT', 587)
        smtp_username = getattr(settings, 'EMAIL_HOST_USER', '')
        smtp_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', smtp_username)
        
        if not smtp_username or not smtp_password:
            logger.warning("Email credentials not configured. Email not sent.")
            return False
        
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = from_email
        message['To'] = to_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        message.attach(html_part)
        
        # Connect to SMTP server and send email
        use_tls = getattr(settings, 'EMAIL_USE_TLS', True)
        
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        
        server.login(smtp_username, smtp_password)
        server.sendmail(from_email, to_email, message.as_string())
        server.quit()
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


def send_password_reset_email(user, reset_token):
    """
    Send password reset email with reset link
    
    Args:
        user: User instance
        reset_token: Password reset token
    
    Returns:
        bool: Success status
    """
    # Build reset URL
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    reset_url = f"{site_url}/reset-password/{reset_token}/"
    
    subject = "Reset Your Seashore Microfinance Password 🔐"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 700;
            }}
            .logo {{
                font-size: 48px;
                margin-bottom: 10px;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .greeting {{
                font-size: 20px;
                font-weight: 600;
                color: #eab308;
                margin-bottom: 20px;
            }}
            .message {{
                font-size: 16px;
                color: #555;
                margin-bottom: 30px;
            }}
            .alert-box {{
                background-color: #fef3c7;
                border-left: 4px solid #eab308;
                padding: 20px;
                margin: 30px 0;
            }}
            .alert-box p {{
                margin: 0;
                color: #92400e;
            }}
            .cta-button {{
                display: inline-block;
                background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%);
                color: white;
                padding: 15px 40px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: 600;
                margin: 20px 0;
                text-align: center;
            }}
            .cta-button:hover {{
                background: linear-gradient(135deg, #ca8a04 0%, #a16207 100%);
            }}
            .token-box {{
                background-color: #f9fafb;
                border: 2px dashed #eab308;
                padding: 20px;
                text-align: center;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .token {{
                font-size: 24px;
                font-weight: 700;
                color: #eab308;
                letter-spacing: 2px;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 30px;
                text-align: center;
                font-size: 14px;
                color: #666;
            }}
            .footer a {{
                color: #eab308;
                text-decoration: none;
            }}
            .divider {{
                height: 1px;
                background-color: #e5e7eb;
                margin: 30px 0;
            }}
            .security-notice {{
                background-color: #fef2f2;
                border-left: 4px solid #ef4444;
                padding: 15px;
                margin-top: 30px;
            }}
            .security-notice p {{
                margin: 5px 0;
                color: #991b1b;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🏦</div>
                <h1>Password Reset Request</h1>
            </div>
            
            <div class="content">
                <div class="greeting">
                    Hello {user.get_full_name() or user.email}! 👋
                </div>
                
                <div class="message">
                    <p>We received a request to reset the password for your Seashore Microfinance account.</p>
                    
                    <p>If you made this request, click the button below to reset your password:</p>
                </div>
                
                <div style="text-align: center;">
                    <a href="{reset_url}" class="cta-button">
                        🔐 Reset Password
                    </a>
                </div>
                
                <div class="alert-box">
                    <p><strong>⏰ This link will expire in 1 hour</strong></p>
                </div>
                
                <div class="divider"></div>
                
                <div class="message">
                    <p><strong>Can't click the button?</strong> Copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #eab308;">
                        {reset_url}
                    </p>
                </div>
                
                <div class="security-notice">
                    <p><strong>⚠️ Security Notice:</strong></p>
                    <p>• If you didn't request this password reset, please ignore this email</p>
                    <p>• Never share your password with anyone</p>
                    <p>• Seashore staff will never ask for your password</p>
                </div>
            </div>
            
            <div class="footer">
                <p><strong>Seashore Microfinance Bank</strong></p>
                <p>Professional Microfinance Solutions</p>
                <p style="margin-top: 20px; font-size: 12px; color: #999;">
                    This email was sent to {user.email}. If you have any questions, contact support.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(user.email, subject, html_content)


def send_welcome_email(user):
    """
    Send welcome email to new user
    
    Args:
        user: User instance
    
    Returns:
        bool: Success status
    """
    subject = "Welcome to Seashore Microfinance! 🎉"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 700;
            }}
            .logo {{
                font-size: 64px;
                margin-bottom: 10px;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .greeting {{
                font-size: 20px;
                font-weight: 600;
                color: #eab308;
                margin-bottom: 20px;
            }}
            .message {{
                font-size: 16px;
                color: #555;
                margin-bottom: 30px;
            }}
            .features {{
                background-color: #fefce8;
                border-left: 4px solid #eab308;
                padding: 20px;
                margin: 30px 0;
            }}
            .features h3 {{
                color: #eab308;
                margin-top: 0;
            }}
            .features ul {{
                margin: 10px 0;
                padding-left: 20px;
            }}
            .features li {{
                margin: 8px 0;
                color: #555;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 30px;
                text-align: center;
                font-size: 14px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🏦</div>
                <h1>Welcome to Seashore Microfinance</h1>
            </div>
            
            <div class="content">
                <div class="greeting">
                    Hello {user.get_full_name() or 'Team Member'}! 👋
                </div>
                
                <div class="message">
                    <p>Welcome to <strong>Seashore Microfinance Bank</strong>!</p>
                    
                    <p>Your account as <strong>{user.get_user_role_display()}</strong> has been created successfully. You're now part of our team!</p>
                </div>
                
                <div class="features">
                    <h3>🚀 Getting Started</h3>
                    <ul>
                        <li><strong>Log in</strong> with your credentials</li>
                        <li><strong>Complete your profile</strong> with required information</li>
                        <li><strong>Review your dashboard</strong> based on your role</li>
                        <li><strong>Access training materials</strong> in the knowledge base</li>
                    </ul>
                </div>
                
                <div class="message">
                    <p><strong>Your Role: {user.get_user_role_display()}</strong></p>
                    <p>Branch: {user.branch.name if user.branch else 'Not assigned'}</p>
                    <p>Employee ID: {user.employee_id}</p>
                </div>
            </div>
            
            <div class="footer">
                <p><strong>Seashore Microfinance Bank</strong></p>
                <p>Professional Microfinance Solutions</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(user.email, subject, html_content)


def send_client_approval_email(client):
    """
    Send email to client when their account is approved
    
    Args:
        client: Client instance
    
    Returns:
        bool: Success status
    """
    subject = "Your Seashore Account Has Been Approved! ✅"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .content {{
                background: white;
                padding: 30px;
                border: 1px solid #ddd;
            }}
            .highlight {{
                background-color: #fefce8;
                padding: 15px;
                border-left: 4px solid #eab308;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Account Approved!</h1>
            </div>
            <div class="content">
                <p>Dear {client.get_full_name()},</p>
                
                <p>Congratulations! Your Seashore Microfinance account has been approved.</p>
                
                <div class="highlight">
                    <p><strong>Account Details:</strong></p>
                    <p>Client ID: {client.client_id}</p>
                    <p>Level: {client.get_level_display()}</p>
                    <p>Branch: {client.branch.name}</p>
                </div>
                
                <p>You can now:</p>
                <ul>
                    <li>Apply for loans up to ₦{client.get_loan_limit():,.2f}</li>
                    <li>Open savings accounts</li>
                    <li>Access our full range of financial services</li>
                </ul>
                
                <p>Visit your nearest branch to get started!</p>
                
                <p>Best regards,<br>Seashore Microfinance Team</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(client.email, subject, html_content)


def send_loan_approval_email(loan):
    """
    Send email when loan is approved
    
    Args:
        loan: Loan instance
    
    Returns:
        bool: Success status
    """
    subject = "Your Loan Has Been Approved! 🎊"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .content {{
                background: white;
                padding: 30px;
                border: 1px solid #ddd;
            }}
            .loan-details {{
                background-color: #f0fdf4;
                padding: 20px;
                border-left: 4px solid #22c55e;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Loan Approved!</h1>
            </div>
            <div class="content">
                <p>Dear {loan.client.get_full_name()},</p>
                
                <p>Great news! Your loan application has been approved.</p>
                
                <div class="loan-details">
                    <p><strong>Loan Details:</strong></p>
                    <p>Loan Number: {loan.loan_number}</p>
                    <p>Principal Amount: ₦{loan.principal_amount:,.2f}</p>
                    <p>Total Repayment: ₦{loan.total_repayment:,.2f}</p>
                    <p>Monthly Installment: ₦{loan.installment_amount:,.2f}</p>
                    <p>Duration: {loan.duration_months} months</p>
                </div>
                
                <p>The funds will be disbursed to your account shortly.</p>
                
                <p>Best regards,<br>Seashore Microfinance Team</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(loan.client.email, subject, html_content)