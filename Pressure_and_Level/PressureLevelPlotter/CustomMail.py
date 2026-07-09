from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import json
import os
import sys
from datetime import datetime
from typing import Optional
import re

_COMMON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "common"))
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

from paths import writable_path

MAIL_LOG_FILE = "maillog_pressurelevel.txt"


def resource_path(relative_path):
    """Writable path next to the app (mail config / mail log)."""
    return writable_path(relative_path)


def _quote(value: str) -> str:
    return '"' + str(value).replace('"', "'") + '"'


def write_mail_log(
    status: str,
    stage: str,
    *,
    subject: Optional[str] = None,
    recipients: Optional[int] = None,
    smtp: Optional[str] = None,
    user: Optional[str] = None,
    detail: Optional[str] = None,
    log_file: str = MAIL_LOG_FILE,
) -> None:
    """
    Write a structured mail log line.

    Format:
      [time] [SUCCESS|FAIL] stage=... subject="..." recipients=N smtp=host:port user=... detail=...
    """
    try:
        log_path = resource_path(log_file)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        parts = [f"[{current_time}]", f"[{status}]", f"stage={stage}"]
        if subject is not None:
            parts.append(f"subject={_quote(subject)}")
        if recipients is not None:
            parts.append(f"recipients={recipients}")
        if smtp is not None:
            parts.append(f"smtp={smtp}")
        if user is not None:
            parts.append(f"user={user}")
        if detail is not None:
            parts.append(f"detail={detail}")
        with open(log_path, 'a', encoding='utf-8') as file:
            file.write(' '.join(parts) + '\n')
    except Exception as e:
        print(f"Failed to write mail log: {e}")


def write_log(message: str, log_file: str = MAIL_LOG_FILE):
    """Backward-compatible free-form mail log writer (tests / ad-hoc). """
    try:
        log_path = resource_path(log_file)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f'[{current_time}] {message}\n'
        with open(log_path, 'a', encoding='utf-8') as file:
            file.write(log_message)
    except Exception as e:
        print(f"Failed to write log: {e}")


def validate_email(email: str) -> bool:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False

    # Remove whitespace
    email = email.strip()

    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def load_config() -> dict:
    """
    Load email configuration from JSON file.

    Returns:
        Dictionary containing SMTP settings and recipient list

    Raises:
        FileNotFoundError: If config file is not found
        json.JSONDecodeError: If config file is invalid JSON
        KeyError: If required keys are missing
    """
    config_path = resource_path("mail_config.json")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        write_mail_log(
            "FAIL",
            "config_load",
            detail="Email configuration file not found. Please create mail_config.json",
        )
        raise
    except json.JSONDecodeError as e:
        write_mail_log(
            "FAIL",
            "config_load",
            detail=f"Invalid JSON format in mail_config.json: {e}",
        )
        raise

    # Validate required keys
    required_keys = ['smtp_server', 'smtp_port', 'smtp_user', 'smtp_password', 'recipients']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        write_mail_log(
            "FAIL",
            "config_load",
            detail=f"Missing required keys in mail_config.json: {', '.join(missing_keys)}",
        )
        raise KeyError(f"Missing required keys: {', '.join(missing_keys)}")

    # Validate recipients
    if not isinstance(config['recipients'], list) or len(config['recipients']) == 0:
        write_mail_log(
            "FAIL",
            "recipient_validate",
            detail="Recipients list is empty or invalid",
        )
        raise ValueError("Recipients list must be a non-empty list")

    return config


def create_email_message(sender: str, recipients: list, subject: str, content: str, sender_name: Optional[str] = None) -> MIMEMultipart:
    """
    Create email message object.

    Args:
        sender: Sender email address
        recipients: List of recipient email addresses
        subject: Email subject
        content: Email content
        sender_name: Optional sender display name

    Returns:
        MIMEMultipart message object

    Raises:
        ValueError: If email addresses are invalid
    """
    # Validate sender
    if not validate_email(sender):
        raise ValueError(f"Invalid sender email address: {sender}")

    # Validate recipients
    invalid_recipients = [r for r in recipients if not validate_email(r)]
    if invalid_recipients:
        raise ValueError(f"Invalid recipient email addresses: {', '.join(invalid_recipients)}")

    # Format From field with optional sender name
    if sender_name and sender_name.strip():
        from_field = f"{sender_name.strip()} <{sender}>"
    else:
        from_field = sender

    # Create message
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = from_field
    msg['To'] = ', '.join(recipients)
    msg.attach(MIMEText(content, 'plain', 'utf-8'))

    return msg


def send_mail(subject: str, content: str) -> tuple[bool, Optional[str]]:
    """
    Send email using SMTP.

    Args:
        subject: Email subject (will be used as provided)
        content: Email content (will be used as provided)

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - If successful: (True, None)
        - If failed: (False, error_message)
    """
    smtp_server = None
    smtp_port = None
    smtp_user = None
    recipients: list[str] = []

    try:
        # Load configuration
        try:
            config = load_config()
        except FileNotFoundError as e:
            error_msg = f"Configuration file not found: {e}"
            write_mail_log("FAIL", "config_load", subject=subject, detail=error_msg)
            return False, error_msg
        except (json.JSONDecodeError, KeyError) as e:
            error_msg = f"Configuration error: {e}"
            write_mail_log("FAIL", "config_load", subject=subject, detail=error_msg)
            return False, error_msg
        except ValueError as e:
            error_msg = f"Configuration error: {e}"
            write_mail_log("FAIL", "recipient_validate", subject=subject, detail=error_msg)
            return False, error_msg

        smtp_server = config['smtp_server']
        smtp_port = config['smtp_port']
        smtp_user = config['smtp_user']
        smtp_password = config['smtp_password']
        sender_name = config.get('sender_name', None)  # Optional field
        smtp_label = f"{smtp_server}:{smtp_port}"

        # Process recipients: handle multiple recipients safely
        for r in config['recipients']:
            # Skip None or non-string values
            if r is None:
                continue
            if not isinstance(r, str):
                write_mail_log(
                    "FAIL",
                    "recipient_validate",
                    subject=subject,
                    smtp=smtp_label,
                    user=smtp_user,
                    detail=f"Warning: Skipping invalid recipient type: {type(r).__name__}",
                )
                continue

            # Clean and process string recipient
            cleaned = r.strip().replace('\n', '').replace('\r', '')
            if cleaned:  # Only add non-empty strings
                recipients.append(cleaned)

        # Validate recipients after cleaning
        if not recipients:
            error_msg = "No valid recipients found after processing"
            write_mail_log(
                "FAIL",
                "recipient_validate",
                subject=subject,
                smtp=smtp_label,
                user=smtp_user,
                detail=error_msg,
            )
            return False, error_msg

        # Create email message
        try:
            msg = create_email_message(smtp_user, recipients, subject, content, sender_name)
        except ValueError as e:
            error_msg = f"Message build error: {e}"
            write_mail_log(
                "FAIL",
                "message_build",
                subject=subject,
                recipients=len(recipients),
                smtp=smtp_label,
                user=smtp_user,
                detail=error_msg,
            )
            return False, error_msg

        # Send email using context manager for proper resource cleanup
        try:
            with smtplib.SMTP_SSL(host=smtp_server, port=smtp_port) as smtp_conn:
                try:
                    smtp_conn.login(smtp_user, smtp_password)
                except smtplib.SMTPException as e:
                    error_msg = f"SMTP login error: {e}"
                    write_mail_log(
                        "FAIL",
                        "smtp_login",
                        subject=subject,
                        recipients=len(recipients),
                        smtp=smtp_label,
                        user=smtp_user,
                        detail=error_msg,
                    )
                    return False, error_msg

                try:
                    for recipient in recipients:
                        smtp_conn.sendmail(smtp_user, recipient, msg.as_string())
                except smtplib.SMTPException as e:
                    error_msg = f"SMTP send error: {e}"
                    write_mail_log(
                        "FAIL",
                        "smtp_send",
                        subject=subject,
                        recipients=len(recipients),
                        smtp=smtp_label,
                        user=smtp_user,
                        detail=error_msg,
                    )
                    return False, error_msg
        except smtplib.SMTPException as e:
            error_msg = f"SMTP connect error: {e}"
            write_mail_log(
                "FAIL",
                "smtp_connect",
                subject=subject,
                recipients=len(recipients),
                smtp=smtp_label,
                user=smtp_user,
                detail=error_msg,
            )
            return False, error_msg

        write_mail_log(
            "SUCCESS",
            "smtp_send",
            subject=subject,
            recipients=len(recipients),
            smtp=smtp_label,
            user=smtp_user,
        )
        return True, None

    except Exception as e:
        error_msg = f"Unexpected error occurred while sending email: {e}"
        smtp_label = (
            f"{smtp_server}:{smtp_port}" if smtp_server is not None and smtp_port is not None else None
        )
        write_mail_log(
            "FAIL",
            "smtp_send",
            subject=subject,
            recipients=len(recipients) if recipients else None,
            smtp=smtp_label,
            user=smtp_user,
            detail=error_msg,
        )
        return False, error_msg
