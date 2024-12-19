import os
import smtplib
import logging
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def send_error_email(subject, message, to_email):
    from_email = os.getenv("FROM_EMAIL")
    email_password = os.getenv("EMAIL_PASSWORD")
    
    if not from_email or not email_password:
        logging.warning("Email credentials not provided. Skipping error email.")
        return

    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(from_email, email_password)
            server.send_message(msg)
        logging.info("Error notification email sent.")
    except Exception as e:
        logging.error(f"Failed to send error email: {e}")
