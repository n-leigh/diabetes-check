"""Send one standalone verification-style email to an explicitly supplied address."""

import argparse
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urljoin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="The one address that should receive the test message.")
    args = parser.parse_args()
    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "BASE_URL")
    if not all(os.getenv(name, "").strip() for name in required):
        print("failure: required email configuration is missing")
        return 1
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
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(os.environ["SMTP_HOST"].strip(), int(os.environ["SMTP_PORT"]), timeout=10) as server:
            server.starttls(context=context)
            server.login(os.environ["SMTP_USER"].strip(), os.environ["SMTP_PASSWORD"])
            server.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError):
        print("failure: email could not be sent")
        return 1
    print("success: test email sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
