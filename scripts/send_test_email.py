"""Send one standalone verification-style email to an explicitly supplied address."""

import argparse
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urljoin

from dotenv import load_dotenv

load_dotenv()


def _diagnose(error):
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "SMTP login rejected: set SMTP_USER to the login shown on Brevo's SMTP & API page and SMTP_PASSWORD to an SMTP key (not an API key or account password)"
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return "SMTP recipient refused: check the recipient address and Brevo sending restrictions"
    if isinstance(error, smtplib.SMTPSenderRefused):
        return "SMTP_FROM must be a verified sender in Brevo"
    if isinstance(error, TimeoutError):
        return "SMTP connection timed out: check host, port, TLS, or firewall settings"
    if isinstance(error, OSError):
        return "SMTP connection failed: check host, port, TLS, or firewall settings"
    if isinstance(error, smtplib.SMTPResponseException):
        reason = error.smtp_error.decode("utf-8", "replace") if isinstance(error.smtp_error, bytes) else str(error.smtp_error)
        if "not activated" in reason.lower():
            return "Brevo has not activated SMTP sending on this account; contact Brevo support"
        return f"SMTP error {error.smtp_code}: {reason}"
    return f"{type(error).__name__}: {error}"


def _config_error():
    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "BASE_URL")
    for name in required:
        value = os.getenv(name)
        if not value or not value.strip():
            return f"{name} is empty"
        if value != value.strip() or (len(value) >= 2 and value[0] == value[-1] == '"'):
            return f"{name} has surrounding spaces or quotes"
        if any(marker in value.lower() for marker in ("replace", "password", "your_")) or "(" in value or ")" in value:
            return f"{name} looks like a placeholder"
    if os.getenv("SMTP_PORT", "").strip() != "587":
        return "SMTP_PORT must be 587 when using STARTTLS"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", help="The one address that should receive the test message.")
    parser.add_argument("--check-auth-only", action="store_true", help="Connect and authenticate without sending.")
    args = parser.parse_args()
    if not args.check_auth_only and not args.to:
        parser.error("--to is required unless --check-auth-only is used")
    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "BASE_URL")
    if not all(os.getenv(name, "").strip() for name in required):
        print("failure: required email configuration is missing")
        return 1
    config_error = _config_error()
    if config_error:
        print(f"failure: {config_error}")
        return 1
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(os.environ["SMTP_HOST"].strip(), int(os.environ["SMTP_PORT"]), timeout=10) as server:
            server.starttls(context=context)
            server.login(os.environ["SMTP_USER"].strip(), os.environ["SMTP_PASSWORD"])
            if not args.check_auth_only:
                link = urljoin(os.environ["BASE_URL"].rstrip("/") + "/", "verify-email/test-message")
                message = EmailMessage()
                message["Subject"] = "DiaBeates email delivery test"
                message["From"] = os.environ["SMTP_FROM"].strip()
                message["To"] = args.to.strip()
                message.set_content(f"DiaBeates email delivery test.\n\nVerification-style link:\n{link}\n")
                message.add_alternative(
                    f"<p>DiaBeates email delivery test.</p><p><a href=\"{link}\">Open verification-style link</a></p>",
                    subtype="html",
                )
                server.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as error:
        print(f"failure: {_diagnose(error)}")
        return 1
    print("success: SMTP authentication passed" if args.check_auth_only else "success: test email sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
