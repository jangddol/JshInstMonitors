"""
Test file for CustomMail.py
Run this file with Python debugger to test all functions.
Set breakpoints as needed to inspect values.
"""

import sys
import os

# Add current directory to path to import CustomMail
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from CustomMail import (
    resource_path,
    write_log,
    validate_email,
    load_config,
    create_email_message,
    send_mail
)


def test_resource_path():
    """Test resource_path() function"""
    print("\n" + "="*60)
    print("TEST 1: resource_path()")
    print("="*60)
    
    test_files = ["mail_config.json", "test_file.txt", "nonexistent.txt"]
    for file in test_files:
        path = resource_path(file)
        print(f"  Input: '{file}'")
        print(f"  Output: '{path}'")
        print(f"  Exists: {os.path.exists(path)}")
        print()


def test_write_log():
    """Test write_log() function"""
    print("\n" + "="*60)
    print("TEST 2: write_log()")
    print("="*60)
    
    # Test normal log
    print("  Writing test log message...")
    write_log("Test log message from test_custommail.py")
    print("  ✓ Log written successfully")
    
    # Test custom log file
    print("\n  Writing to custom log file...")
    write_log("Test log to custom file", "test_log.txt")
    print("  ✓ Custom log written successfully")
    
    # Test invalid path (should handle gracefully)
    print("\n  Testing error handling...")
    write_log("This should fail gracefully", "/invalid/path/log.txt")
    print("  ✓ Error handled gracefully")


def test_validate_email():
    """Test validate_email() function"""
    print("\n" + "="*60)
    print("TEST 3: validate_email()")
    print("="*60)
    
    test_cases = [
        # (email, expected_result, description)
        ("test@example.com", True, "Valid email"),
        ("user.name@domain.co.kr", True, "Valid email with subdomain"),
        ("invalid.email", False, "Missing @ symbol"),
        ("@domain.com", False, "Missing local part"),
        ("user@", False, "Missing domain"),
        ("user@domain", False, "Missing TLD"),
        ("", False, "Empty string"),
        (None, False, "None value"),
        ("  test@example.com  ", True, "Email with whitespace (should be trimmed)"),
        ("test+tag@example.com", True, "Email with + sign"),
        ("test.user@example-domain.com", True, "Email with dots and dash"),
    ]
    
    for email, expected, description in test_cases:
        try:
            result = validate_email(email)
            status = "✓" if result == expected else "✗"
            print(f"  {status} {description}")
            print(f"    Input: {repr(email)}")
            print(f"    Expected: {expected}, Got: {result}")
            if result != expected:
                print(f"    ⚠ MISMATCH!")
        except Exception as e:
            print(f"  ✗ {description}")
            print(f"    Error: {e}")
        print()


def test_load_config():
    """Test load_config() function"""
    print("\n" + "="*60)
    print("TEST 4: load_config()")
    print("="*60)
    
    try:
        config = load_config()
        print("  ✓ Configuration loaded successfully")
        print(f"  SMTP Server: {config.get('smtp_server', 'N/A')}")
        print(f"  SMTP Port: {config.get('smtp_port', 'N/A')}")
        print(f"  SMTP User: {config.get('smtp_user', 'N/A')}")
        print(f"  SMTP Password: {'*' * len(config.get('smtp_password', ''))} (hidden)")
        print(f"  Sender Name: {config.get('sender_name', 'Not set')}")
        print(f"  Recipients: {config.get('recipients', [])}")
        print(f"  Number of recipients: {len(config.get('recipients', []))}")
    except FileNotFoundError as e:
        print(f"  ✗ Configuration file not found: {e}")
    except json.JSONDecodeError as e:
        print(f"  ✗ Invalid JSON format: {e}")
    except KeyError as e:
        print(f"  ✗ Missing required key: {e}")
    except ValueError as e:
        print(f"  ✗ Invalid value: {e}")
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")


def test_create_email_message():
    """Test create_email_message() function"""
    print("\n" + "="*60)
    print("TEST 5: create_email_message()")
    print("="*60)
    
    # Test case 1: Without sender_name
    print("  Test 5.1: Without sender_name")
    try:
        msg1 = create_email_message(
            sender="test@example.com",
            recipients=["recipient1@example.com", "recipient2@example.com"],
            subject="Test Subject",
            content="Test content"
        )
        print("  ✓ Email message created successfully")
        print(f"    From: {msg1['From']}")
        print(f"    To: {msg1['To']}")
        print(f"    Subject: {msg1['Subject']}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    print()
    
    # Test case 2: With sender_name
    print("  Test 5.2: With sender_name")
    try:
        msg2 = create_email_message(
            sender="test@example.com",
            recipients=["recipient@example.com"],
            subject="Test Subject with Name",
            content="Test content with sender name",
            sender_name="Test Sender Name"
        )
        print("  ✓ Email message created successfully")
        print(f"    From: {msg2['From']}")
        print(f"    To: {msg2['To']}")
        print(f"    Subject: {msg2['Subject']}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    print()
    
    # Test case 3: Invalid sender email
    print("  Test 5.3: Invalid sender email")
    try:
        msg3 = create_email_message(
            sender="invalid-email",
            recipients=["recipient@example.com"],
            subject="Test",
            content="Test"
        )
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
    
    print()
    
    # Test case 4: Invalid recipient email
    print("  Test 5.4: Invalid recipient email")
    try:
        msg4 = create_email_message(
            sender="test@example.com",
            recipients=["valid@example.com", "invalid-email"],
            subject="Test",
            content="Test"
        )
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")


def test_send_mail(dry_run=True):
    """
    Test send_mail() function
    
    Args:
        dry_run: If True, only test configuration loading and message creation
                 without actually sending email. Set to False to send real email.
    """
    print("\n" + "="*60)
    print("TEST 6: send_mail()")
    print("="*60)
    
    if dry_run:
        print("  ⚠ DRY RUN MODE: Will not send actual email")
        print("  Set dry_run=False to send real email")
        print()
    
    test_subject = "Test Email from CustomMail Test Suite"
    test_content = """This is a test email from the CustomMail test suite.

If you receive this email, the send_mail() function is working correctly.

Test details:
- Subject: Test Email from CustomMail Test Suite
- Content: This test message
- Timestamp: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"  Subject: {test_subject}")
    print(f"  Content preview: {test_content[:50]}...")
    print()
    
    if dry_run:
        # In dry run mode, test configuration loading and message creation
        try:
            config = load_config()
            print("  ✓ Configuration loaded")
            
            smtp_user = config['smtp_user']
            sender_name = config.get('sender_name', None)
            recipients = [r.strip() for r in config['recipients'] if r.strip()]
            recipients = [r.replace('\n', '').replace('\r', '') for r in recipients]
            
            print(f"  Sender: {smtp_user}")
            if sender_name:
                print(f"  Sender Name: {sender_name}")
            print(f"  Recipients: {recipients}")
            
            # Test message creation
            msg = create_email_message(
                sender=smtp_user,
                recipients=recipients,
                subject=test_subject,
                content=test_content,
                sender_name=sender_name
            )
            print("  ✓ Email message created successfully")
            print(f"    From: {msg['From']}")
            print(f"    To: {msg['To']}")
            print()
            print("  ⚠ Skipping actual SMTP send (dry_run=True)")
            print("  To send real email, call: test_send_mail(dry_run=False)")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        # Actually send email
        print("  ⚠ SENDING REAL EMAIL...")
        result = send_mail(test_subject, test_content)
        if result:
            print("  ✓ Email sent successfully!")
        else:
            print("  ✗ Failed to send email. Check logs for details.")


def run_all_tests():
    """Run all tests"""
    print("\n" + "#"*60)
    print("# CustomMail.py Test Suite")
    print("#"*60)
    
    test_resource_path()
    test_write_log()
    test_validate_email()
    test_load_config()
    test_create_email_message()
    test_send_mail(dry_run=False)  # Set to False to send real email
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETED")
    print("="*60)
    print("\nTo send a real email, call:")
    print("  test_send_mail(dry_run=False)")
    print()


if __name__ == "__main__":
    # Import datetime for test_send_mail
    from datetime import datetime
    import json
    
    # Run all tests
    run_all_tests()
    
    # Uncomment the line below to send a real email (use with caution!)
    # test_send_mail(dry_run=False)

