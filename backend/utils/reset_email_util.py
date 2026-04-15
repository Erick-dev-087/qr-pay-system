import smtplib
import time
from email.message import EmailMessage
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

from flask import current_app


class ResetEmail:
        def __init__(self, reset_url, token, recipient_email):
                self.reset_url = (reset_url or "").strip()
                self.token = str(token or "").strip()
                self.recipient = (recipient_email or "").strip()

        def _build_reset_link(self):
            raw_url = (self.reset_url or "").strip()
            if not raw_url:
                return ""

            # Make Vercel-style bare hosts usable in email links.
            if not raw_url.lower().startswith(("http://", "https://")):
                raw_url = f"https://{raw_url}"

            parsed = urlsplit(raw_url)
            normalized_path = parsed.path or "/reset-password"
            if normalized_path == "/":
                normalized_path = "/reset-password"

            normalized_url = urlunsplit(
                (parsed.scheme, parsed.netloc, normalized_path, parsed.query, parsed.fragment)
            )

            if "{token}" in normalized_url:
                return normalized_url.replace("{token}", quote_plus(self.token))

            split = urlsplit(normalized_url)
            query_pairs = dict(parse_qsl(split.query, keep_blank_values=True))
            query_pairs["token"] = self.token
            encoded_query = urlencode(query_pairs)
            return urlunsplit((split.scheme, split.netloc, split.path, encoded_query, split.fragment))

        def build_email_body(self):
                brand_name = (current_app.config.get("APP_BRAND_NAME") or "ScanPay").strip()
                expires_in_seconds = int(current_app.config.get("PASSWORD_RESET_EXPIRES_SECONDS", 3600))
                expires_in_minutes = max(1, expires_in_seconds // 60)
                reset_link = self._build_reset_link()

                link_section = ""
                if reset_link:
                        link_section = f"""
                            <tr>
                                <td style="padding: 0 36px 8px 36px; text-align: center;">
                                    <a href=\"{reset_link}\" style="display:inline-block; background: linear-gradient(135deg, #00FF7F, #00D094); color:#03121A; text-decoration:none; font-weight:700; font-size:15px; letter-spacing:0.2px; padding:14px 26px; border-radius:12px;">Reset Password Securely</a>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 12px 36px 0 36px; color:#A0B4CC; font-size:12px; line-height:1.6;">
                                    If the button does not work, copy and paste this secure link into your browser:<br>
                                    <a href=\"{reset_link}\" style="color:#D9F5E8; word-break:break-all; text-decoration:underline;">{reset_link}</a>
                                </td>
                            </tr>
                        """
                else:
                        link_section = """
                            <tr>
                                <td style="padding: 12px 36px 0 36px; color:#F7B267; font-size:12px; line-height:1.6;">
                                    Reset link is unavailable because PASSWORD_RESET_FRONTEND_URL is not configured on the server.
                                </td>
                            </tr>
                        """

                return f"""
<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{brand_name} Password Reset</title>
    </head>
    <body style="margin:0; padding:0; background:#081229; font-family:'Segoe UI', Tahoma, Arial, sans-serif;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#081229; padding:24px 12px;">
            <tr>
                <td align="center">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px; background:#0B132B; border:1px solid #163153; border-radius:16px; overflow:hidden; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);">
                        <tr>
                            <td style="padding:28px 36px 16px 36px; background:radial-gradient(circle at top right, rgba(0,255,127,0.18), rgba(11,19,43,1) 45%);">
                                <div style="font-size:13px; color:#9CC9B8; letter-spacing:1.2px; text-transform:uppercase; font-weight:600;">Security Notice</div>
                                <h1 style="margin:10px 0 0 0; color:#F5FAFF; font-size:28px; line-height:1.2;">Reset your {brand_name} password</h1>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 24px 36px 8px 36px; color:#D4E2F0; font-size:15px; line-height:1.7;">
                                We received a request to reset your password. Use the secure token below to continue. This token expires in <strong style="color:#00D094;">{expires_in_minutes} minutes</strong>.
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 36px 4px 36px;">
                                <div style="background:#0F1A36; border:1px solid #1F3D62; border-radius:12px; padding:14px 16px;">
                                    <div style="color:#9BB1C8; font-size:12px; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.8px;">Reset Token</div>
                                    <div style="color:#00FF7F; font-size:14px; line-height:1.6; font-family:Consolas, Monaco, 'Courier New', monospace; word-break:break-all;">{self.token}</div>
                                </div>
                            </td>
                        </tr>
                        {link_section}
                        <tr>
                            <td style="padding: 20px 36px 0 36px; color:#A0B4CC; font-size:13px; line-height:1.7;">
                                If you did not request this, you can safely ignore this email. Your account remains protected.
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 24px 36px 30px 36px; color:#7F95AE; font-size:12px; border-top:1px solid #142A47; margin-top:20px;">
                                {brand_name} Security Team<br>
                                This is an automated message. Please do not reply.
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
</html>
                """.strip()

        def _build_plain_text_body(self):
                brand_name = (current_app.config.get("APP_BRAND_NAME") or "ScanPay").strip()
                reset_link = self._build_reset_link()
                expires_in_seconds = int(current_app.config.get("PASSWORD_RESET_EXPIRES_SECONDS", 3600))
                expires_in_minutes = max(1, expires_in_seconds // 60)

                parts = [
                        f"{brand_name} password reset request",
                        "",
                        f"Reset token: {self.token}",
                        f"This token expires in {expires_in_minutes} minutes.",
                ]

                if reset_link:
                        parts.append(f"Reset link: {reset_link}")

                parts.extend(
                        [
                                "",
                                "If you did not request this, you can ignore this email.",
                        ]
                )
                return "\n".join(parts)

        def send_reset_email(self):
                subject = "Reset Your ScanPay Password"
                html_body = self.build_email_body()
                plain_body = self._build_plain_text_body()

                config = current_app.config
                mail_server = (config.get("MAIL_SERVER") or "").strip()
                mail_port = int(config.get("MAIL_PORT") or 0)
                mail_username = (config.get("MAIL_USERNAME") or "").strip()
                mail_password = (config.get("MAIL_PASSWORD") or "").strip()
                mail_default_sender = (config.get("MAIL_DEFAULT_SENDER") or mail_username).strip()
                mail_use_tls = bool(config.get("MAIL_USE_TLS", True))
                mail_use_ssl = bool(config.get("MAIL_USE_SSL", False))
                mail_timeout = int(config.get("MAIL_TIMEOUT_SECONDS") or 20)
                max_retries = max(1, int(config.get("MAIL_SEND_MAX_RETRIES") or 3))
                retry_backoff_seconds = float(config.get("MAIL_RETRY_BACKOFF_SECONDS") or 1.0)

                if not self.recipient:
                        return "Failed to send email: recipient email is missing"

                if not mail_server or not mail_port:
                        return "Failed to send email: MAIL_SERVER or MAIL_PORT is not configured"

                if not mail_default_sender:
                        return "Failed to send email: MAIL_DEFAULT_SENDER or MAIL_USERNAME is not configured"

                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = mail_default_sender
                msg["To"] = self.recipient
                msg.set_content(plain_body)
                msg.add_alternative(html_body, subtype="html")

                last_error = None
                transient_os_errors = {101, 110, 111, 113}

                for attempt in range(1, max_retries + 1):
                    try:
                        smtp_cls = smtplib.SMTP_SSL if mail_use_ssl else smtplib.SMTP
                        with smtp_cls(mail_server, mail_port, timeout=mail_timeout) as smtp:
                            smtp.ehlo()
                            if mail_use_tls and not mail_use_ssl:
                                smtp.starttls()
                                smtp.ehlo()
                            if mail_username and mail_password:
                                smtp.login(mail_username, mail_password)
                            smtp.send_message(msg)
                        return True
                    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError) as exc:
                        last_error = exc
                        if attempt < max_retries:
                            current_app.logger.warning(
                                "SMTP connection issue on attempt %s/%s for %s: %s",
                                attempt,
                                max_retries,
                                self.recipient,
                                exc,
                            )
                            time.sleep(max(0.0, retry_backoff_seconds) * attempt)
                            continue
                        break
                    except OSError as exc:
                        last_error = exc
                        err_no = getattr(exc, "errno", None)
                        if attempt < max_retries:
                            if err_no in transient_os_errors:
                                current_app.logger.warning(
                                    "SMTP network issue on attempt %s/%s for %s: %s",
                                    attempt,
                                    max_retries,
                                    self.recipient,
                                    exc,
                                )
                                time.sleep(max(0.0, retry_backoff_seconds) * attempt)
                                continue
                        break
                    except Exception as exc:
                        last_error = exc
                        break

                return (
                    f"Failed to send email to {self.recipient} after {max_retries} attempt(s): {last_error}"
                )


