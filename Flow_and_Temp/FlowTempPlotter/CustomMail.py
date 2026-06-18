from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import json
import os
import sys
from datetime import datetime
from typing import Optional
import re


def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    For PyInstaller: Returns path relative to exe file location.
    For dev: Returns path relative to script location.
    """
    try:
        # Check if running as PyInstaller bundle
        if getattr(sys, 'frozen', False):
            # PyInstaller: Use exe file directory, not temp folder
            # sys.executable points to the exe file location
            base_path = os.path.dirname(sys.executable)
        else:
            # Development: Use script directory
            base_path = os.path.abspath(os.path.dirname(__file__))
    except Exception:
        # Fallback: Use current working directory
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


def write_log(message: str, log_file: str = "maillog.txt"):
    """
    Write log message to log file.
    
    Args:
        message: Log message to write
        log_file: Log file name (default: maillog.txt)
    """
    try:
        log_path = resource_path(log_file)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f'[{current_time}] {message}\n'
        with open(log_path, 'a', encoding='utf-8') as file:
            file.write(log_message)
    except Exception as e:
        # If logging fails, print to console as fallback
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
        write_log("Email configuration file not found. Please create mail_config.json")
        raise
    except json.JSONDecodeError as e:
        write_log(f"Invalid JSON format in mail_config.json: {e}")
        raise
    
    # Validate required keys
    required_keys = ['smtp_server', 'smtp_port', 'smtp_user', 'smtp_password', 'recipients']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        write_log(f"Missing required keys in mail_config.json: {', '.join(missing_keys)}")
        raise KeyError(f"Missing required keys: {', '.join(missing_keys)}")
    
    # Validate recipients
    if not isinstance(config['recipients'], list) or len(config['recipients']) == 0:
        write_log("Recipients list is empty or invalid")
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


def send_mail(subject: str, content: str) -> bool:
    """
    Send email using SMTP.
    
    Args:
        subject: Email subject (will be used as provided)
        content: Email content (will be used as provided)
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Load configuration
        config = load_config()
        
        smtp_server = config['smtp_server']
        smtp_port = config['smtp_port']
        smtp_user = config['smtp_user']
        smtp_password = config['smtp_password']
        sender_name = config.get('sender_name', None)  # Optional field
        recipients = [r.strip() for r in config['recipients'] if r.strip()]  # Remove empty strings and whitespace
        
        # Remove any newline characters from recipients
        recipients = [r.replace('\n', '').replace('\r', '') for r in recipients]
        
        # Validate recipients after cleaning
        if not recipients:
            write_log("No valid recipients found after processing")
            return False
        
        # Log configuration (without password)
        log_message = f"SMTP Server: {smtp_server}, Port: {smtp_port}, User: {smtp_user}"
        if sender_name:
            log_message += f", Sender Name: {sender_name}"
        write_log(log_message)
        
        # Create email message
        msg = create_email_message(smtp_user, recipients, subject, content, sender_name)
        
        # Send email using context manager for proper resource cleanup
        with smtplib.SMTP_SSL(host=smtp_server, port=smtp_port) as smtp_conn:
            smtp_conn.login(smtp_user, smtp_password)
            for recipient in recipients:
                smtp_conn.sendmail(smtp_user, recipient, msg.as_string())
        
        write_log(f"Email sent successfully to {len(recipients)} recipient(s)")
        return True
        
    except FileNotFoundError as e:
        write_log(f"Configuration file not found: {e}")
        return False
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        write_log(f"Configuration error: {e}")
        return False
    except smtplib.SMTPException as e:
        write_log(f"SMTP error occurred while sending email: {e}")
        return False
    except Exception as e:
        write_log(f"Unexpected error occurred while sending email: {e}")
        return False
