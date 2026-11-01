import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Tuple, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """
    Zero-billing Gmail SMTP email service for dispatching team invitations.
    Gracefully falls back to demo mode if credentials are unconfigured or fail.
    Never exposes credentials or tokens in application logs.
    """

    @property
    def is_configured(self) -> bool:
        """
        Returns True if Gmail SMTP credentials are non-empty.
        """
        return bool(settings.SMTP_EMAIL and settings.SMTP_PASSWORD and settings.SMTP_EMAIL.strip())

    def send_invitation_email(
        self,
        recipient_email: str,
        role: str,
        organization_name: str,
        invitation_url: str,
        inviter_name: Optional[str] = None,
        inviter_email: Optional[str] = None,
        expiry_days: int = 7
    ) -> Tuple[bool, str, str]:
        """
        Sends a branded HTML and plain-text invitation email using Gmail SMTP with STARTTLS.

        Returns:
            Tuple[bool, str, str]: (success, delivery_status, message)
            delivery_status values: 'sent', 'unconfigured_demo_fallback', 'failed'
        """
        if not self.is_configured:
            logger.info("SMTP_EMAIL or SMTP_PASSWORD not set. Utilizing unconfigured demo fallback.")
            return False, "unconfigured_demo_fallback", "SMTP not configured; secure fallback link generated."

        sender_email = settings.SMTP_EMAIL.strip()
        sender_name = settings.SMTP_SENDER_NAME or "Inkloom AI"
        formatted_sender = f"{sender_name} <{sender_email}>"

        human_role = role.replace("_", " ").title()
        inviter_display = inviter_name or inviter_email or "An administrator"

        subject = f"Invitation to join {organization_name} on Inkloom AI"

        # Plain text alternative
        plain_text = f"""Hello,

{inviter_display} has invited you ({recipient_email}) to join the {organization_name} workspace on Inkloom AI as a {human_role}.

Inkloom AI is an enterprise brand governance and content integrity platform. To activate your account and join the workspace, please open the following single-use invitation link in your browser:

{invitation_url}

Security Notice:
- This invitation link is unique to your email address and can only be used once.
- This invitation will expire in {expiry_days} days.
- If you did not expect this invitation, you can safely ignore this email.

Best regards,
The Inkloom AI Team
https://ad-governance.web.app
"""

        # Professional, dark-themed HTML version matching Inkloom AI design system
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Invitation to {organization_name}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #0b0f19;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #e2e8f0;
    }}
    .wrapper {{
      width: 100%;
      background-color: #0b0f19;
      padding: 40px 16px;
      box-sizing: border-box;
    }}
    .container {{
      max-width: 560px;
      margin: 0 auto;
      background: #131b2e;
      border: 1px solid rgba(99, 102, 241, 0.25);
      border-radius: 14px;
      overflow: hidden;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
    }}
    .header {{
      background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(168, 85, 247, 0.1) 100%);
      padding: 28px 32px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }}
    .brand {{
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: #ffffff;
      display: inline-block;
    }}
    .brand span {{
      color: #818cf8;
    }}
    .content {{
      padding: 32px;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 600;
      color: #ffffff;
      margin: 0 0 16px 0;
      line-height: 1.35;
    }}
    p {{
      font-size: 14px;
      line-height: 1.6;
      color: #94a3b8;
      margin: 0 0 20px 0;
    }}
    .role-badge {{
      display: inline-block;
      background: rgba(99, 102, 241, 0.15);
      border: 1px solid rgba(99, 102, 241, 0.35);
      color: #c7d2fe;
      font-weight: 600;
      font-size: 13px;
      padding: 3px 10px;
      border-radius: 6px;
    }}
    .btn-container {{
      text-align: center;
      margin: 30px 0;
    }}
    .btn {{
      display: inline-block;
      background: #6366f1;
      color: #ffffff !important;
      text-decoration: none;
      font-weight: 600;
      font-size: 14px;
      padding: 12px 28px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
    }}
    .fallback-box {{
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 8px;
      padding: 14px;
      margin-top: 24px;
      word-break: break-all;
    }}
    .fallback-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #64748b;
      margin-bottom: 6px;
      font-weight: 600;
    }}
    .fallback-url {{
      font-size: 12px;
      color: #818cf8;
      text-decoration: none;
    }}
    .footer {{
      padding: 20px 32px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 12px;
      color: #64748b;
      line-height: 1.5;
      background: rgba(11, 15, 25, 0.5);
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <div class="brand">Inkloom<span>.AI</span></div>
      </div>
      <div class="content">
        <h1>Workspace Invitation</h1>
        <p>
          <strong style="color: #f1f5f9;">{inviter_display}</strong> has invited you to join the
          <strong style="color: #f1f5f9;">{organization_name}</strong> workspace on Inkloom AI with the governance role:
        </p>
        <p style="margin: 12px 0 24px 0;">
          <span class="role-badge">{human_role}</span>
        </p>
        <p>
          Inkloom AI provides multi-tenant brand governance and content integrity. Click below to accept the invitation and establish your workspace access:
        </p>
        <div class="btn-container">
          <a href="{invitation_url}" class="btn" target="_blank" rel="noopener noreferrer">Accept Invitation</a>
        </div>
        <div class="fallback-box">
          <div class="fallback-label">Direct Link Fallback</div>
          <a href="{invitation_url}" class="fallback-url">{invitation_url}</a>
        </div>
      </div>
      <div class="footer">
        <div>• This single-use invitation is valid for <strong>{expiry_days} days</strong>.</div>
        <div>• If you were not expecting this invitation, you can ignore this email.</div>
        <div style="margin-top: 8px;">Inkloom AI &bull; Brand Governance & Content Integrity Platform</div>
      </div>
    </div>
  </div>
</body>
</html>
"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formatted_sender
        msg["To"] = recipient_email
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            logger.info(f"Connecting to SMTP server at {settings.SMTP_HOST}:{settings.SMTP_PORT}...")
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)

            if settings.SMTP_USE_TLS:
                server.starttls()

            password = (settings.SMTP_PASSWORD or "").replace(" ", "").strip()
            server.login(sender_email, password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
            server.quit()

            logger.info(f"Invitation email successfully dispatched to {recipient_email} via SMTP ({settings.SMTP_HOST}).")
            return True, "sent", f"Invitation email successfully sent via SMTP ({settings.SMTP_HOST})."

        except smtplib.SMTPAuthenticationError as auth_err:
            logger.error(f"SMTP authentication failed on {settings.SMTP_HOST}: {auth_err.smtp_code} - {auth_err.smtp_error}")
            return False, "failed", f"SMTP authentication failed on {settings.SMTP_HOST}. Please verify credentials / API key."
        except (smtplib.SMTPException, OSError, TimeoutError) as net_err:
            logger.error(f"SMTP dispatch error for {recipient_email} via {settings.SMTP_HOST}: {type(net_err).__name__} - {str(net_err)}")
            return False, "failed", f"SMTP delivery error: {type(net_err).__name__}."
        except Exception as unexpected_err:
            logger.error(f"Unexpected error in email dispatch: {type(unexpected_err).__name__}")
            return False, "failed", "Unexpected email delivery failure."

email_service = EmailService()
