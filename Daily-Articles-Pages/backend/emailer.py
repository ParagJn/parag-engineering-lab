"""Send Morning Edition magazine via email with PDF attachment."""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Morning Edition")


def _build_digest_html(title: str, tagline: str, stories: list[dict], date_str: str) -> str:
    """Build a lightweight HTML email body with story summaries and links."""
    story_rows = ""
    for i, story in enumerate(stories):
        cat = story.get("category_label", "TECH")
        headline = story.get("headline", "Untitled")
        deck = story.get("deck", "")
        url = story.get("original_url", "#")
        applies = story.get("applies_to_me", False)
        badge = ' <span style="background:#f43f5e;color:#fff;font-size:10px;padding:2px 6px;border-radius:3px;font-weight:700;">APPLIES TO YOU</span>' if applies else ""

        story_rows += f"""
        <tr>
          <td style="padding:20px 0;border-bottom:1px solid #f0f0f0;">
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.15em;color:#6366f1;margin-bottom:4px;">
              {cat}{badge}
            </div>
            <a href="{url}" style="font-family:Georgia,serif;font-size:18px;font-weight:700;color:#1a1a1a;text-decoration:none;line-height:1.3;">
              {headline}
            </a>
            <div style="font-size:14px;color:#737373;margin-top:4px;line-height:1.5;">
              {deck}
            </div>
          </td>
        </tr>"""

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
    <body style="margin:0;padding:0;background:#f5f5f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <div style="max-width:600px;margin:0 auto;background:#ffffff;">

        <!-- Header -->
        <div style="background:#0a0a0a;color:#ffffff;padding:40px 30px;text-align:center;">
          <div style="font-size:12px;text-transform:uppercase;letter-spacing:0.2em;opacity:0.5;margin-bottom:12px;">{date_str}</div>
          <div style="font-family:Georgia,serif;font-size:28px;font-weight:900;line-height:1.1;margin-bottom:8px;">{title}</div>
          <div style="font-size:15px;opacity:0.7;font-weight:300;">{tagline}</div>
        </div>

        <!-- Stories -->
        <div style="padding:10px 30px 30px;">
          <table style="width:100%;border-collapse:collapse;">
            {story_rows}
          </table>
        </div>

        <!-- Footer -->
        <div style="background:#fafaf9;padding:25px 30px;text-align:center;border-top:1px solid #e7e5e4;">
          <div style="font-family:Georgia,serif;font-size:14px;color:#1a1a1a;font-weight:700;margin-bottom:4px;">Morning Edition</div>
          <div style="font-size:12px;color:#a8a29e;">AI-curated by Claude &amp; Gemini &bull; PDF attached for full magazine experience</div>
        </div>
      </div>
    </body>
    </html>
    """


def send_magazine_email(
    to_emails: list[str],
    subject: str,
    title: str,
    tagline: str,
    stories: list[dict],
    date_str: str,
    pdf_bytes: bytes,
    pdf_filename: str,
) -> dict:
    """Send the magazine email with PDF attachment.

    Returns dict with status and detail.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        raise ValueError("SMTP_USER and SMTP_PASSWORD must be set in .env")

    digest_html = _build_digest_html(title, tagline, stories, date_str)

    msg = MIMEMultipart("mixed")
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_USER))
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject

    # HTML body
    html_part = MIMEText(digest_html, "html", "utf-8")
    msg.attach(html_part)

    # PDF attachment
    pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_part.add_header("Content-Disposition", "attachment", filename=pdf_filename)
    msg.attach(pdf_part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_emails, msg.as_string())

    return {"status": "sent", "recipients": len(to_emails)}
