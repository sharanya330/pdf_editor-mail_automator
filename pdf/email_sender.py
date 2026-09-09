"""Automated Email Sender Module.

Dispatches individual and bulk automated emails with attached customized PDFs via SMTP or Brevo HTTP Email API.
Prevents '[Errno 101] Network is unreachable' on cloud hosts (e.g. Railway) where raw SMTP ports are blocked.
"""

import os
import socket
import smtplib
import ssl
import json
import base64
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Optional, List


def load_dotenv_if_exists() -> None:
    """Loads environment variables from .env file into os.environ if not already set."""
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.join(os.getcwd(), ".env"),
        ".env"
    ]
    for env_path in candidates:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
                break
            except Exception:
                pass


# Load .env on import
load_dotenv_if_exists()

# Prioritize AF_INET (IPv4) resolution with graceful fallback
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if family == 0 or family == socket.AF_UNSPEC:
        try:
            return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        except Exception:
            return _orig_getaddrinfo(host, port, family, type, proto, flags)
    return _orig_getaddrinfo(host, port, family, type, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo


def _create_ssl_context() -> ssl.SSLContext:
    """Creates a secure SSL context with fallback to unverified if root certs are missing."""
    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        return ssl._create_unverified_context()


def _send_via_brevo_api(api_key: str, from_email: str, to_email: str, subject: str, body_text: str, pdf_path: str) -> Dict[str, Any]:
    """Dispatches email using Brevo (Sendinblue) HTTP API (Port 443 HTTPS)."""
    try:
        attachments = []
        if pdf_path and os.path.exists(pdf_path):
            filename = os.path.basename(pdf_path)
            with open(pdf_path, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")
            attachments.append({
                "name": filename,
                "content": b64_content
            })

        sender_name = "HR Team"
        payload = {
            "sender": {"email": (from_email or "").strip(), "name": sender_name},
            "to": [{"email": (to_email or "").strip()}],
            "subject": subject,
            "textContent": body_text
        }
        if attachments:
            payload["attachment"] = attachments

        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": api_key,
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:
            ctx = _create_ssl_context()
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8", errors="ignore")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("message") or err_json.get("code") or err_body
            except Exception:
                msg = err_body
            return {"success": False, "error": f"Brevo API Error ({http_err.code}): {msg}", "recipient": to_email}
        except Exception as ssl_err:
            err_str = str(ssl_err)
            if "CERTIFICATE_VERIFY_FAILED" in err_str or "certificate verify failed" in err_str.lower() or "ssl" in err_str.lower():
                unverified_ctx = ssl._create_unverified_context()
                try:
                    resp = urllib.request.urlopen(req, timeout=15, context=unverified_ctx)
                except urllib.error.HTTPError as http_err:
                    err_body = http_err.read().decode("utf-8", errors="ignore")
                    try:
                        err_json = json.loads(err_body)
                        msg = err_json.get("message") or err_json.get("code") or err_body
                    except Exception:
                        msg = err_body
                    return {"success": False, "error": f"Brevo API Error ({http_err.code}): {msg}", "recipient": to_email}
            else:
                raise ssl_err

        with resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "recipient": to_email, "id": data.get("messageId")}
    except Exception as e:
        return {"success": False, "error": f"Brevo API Error: {str(e)}", "recipient": to_email}


def _connect_smtp(smtp_host: str, smtp_port: int, timeout: int = 20) -> smtplib.SMTP:
    """Connects to SMTP server with proper SSL/TLS and EHLO handshake."""
    port_num = int(smtp_port)
    if port_num == 465:
        try:
            ctx = _create_ssl_context()
            server = smtplib.SMTP_SSL(smtp_host, port_num, timeout=timeout, context=ctx)
        except Exception:
            ctx = ssl._create_unverified_context()
            server = smtplib.SMTP_SSL(smtp_host, port_num, timeout=timeout, context=ctx)
        server.ehlo()
        return server
    else:
        server = smtplib.SMTP(smtp_host, port_num, timeout=timeout)
        server.ehlo()
        try:
            ctx = _create_ssl_context()
            server.starttls(context=ctx)
            server.ehlo()
        except Exception:
            try:
                ctx = ssl._create_unverified_context()
                server.starttls(context=ctx)
                server.ehlo()
            except Exception:
                pass  # STARTTLS not supported or already cleartext
        return server


def _format_auth_error(err_msg: str, smtp_host: str, sender_email: str) -> str:
    """Provides actionable diagnostics for authentication failures."""
    host_lower = smtp_host.lower()
    if "535" in err_msg or "authentication failed" in err_msg.lower() or "badcredentials" in err_msg.lower():
        if "gmail" in host_lower or sender_email.lower().endswith("@gmail.com"):
            return (
                f"Gmail Authentication Failed (535): Google blocks standard passwords. "
                "You must use a 16-character Google 'App Password'. "
                "Generate one at: Google Account -> Security -> 2-Step Verification -> App Passwords."
            )
        if "hostinger" in host_lower:
            return (
                f"Hostinger Authentication Failed (535): Incorrect password or username for '{sender_email}'. "
                "Ensure username is your full email address and password matches your Hostinger Webmail password."
            )
        return f"Authentication Failed (535): Invalid username or password for '{sender_email}'. Please check your email credentials."
    
    if "101" in err_msg or "unreachable" in err_msg.lower() or "111" in err_msg or "refused" in err_msg.lower() or "timed out" in err_msg.lower():
        return (
            f"Connection Failed ({smtp_host}): Outbound SMTP port blocked by network/firewall. "
            "Tip: Use a Brevo HTTP API Key ('xkeysib-...') as password for 100% cloud dispatch over Port 443."
        )

    return f"SMTP Connection/Authentication Error ({smtp_host}): {err_msg}"


def test_smtp_connection(
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    sender_email: Optional[str] = None,
    sender_password: Optional[str] = None,
    test_recipient: str = "test@algoryx.in"
) -> Dict[str, Any]:
    """Tests connection and authentication to the SMTP server or HTTP Mail API and sends a test email."""
    load_dotenv_if_exists()

    if sender_email is None:
        sender_email = os.environ.get("SMTP_SENDER_EMAIL", "").strip()
    else:
        sender_email = sender_email.strip()

    if sender_password is None:
        sender_password = os.environ.get("SMTP_SENDER_PASSWORD", "").strip()
    else:
        sender_password = sender_password.strip()


    if not smtp_host:
        smtp_host = os.environ.get("SMTP_HOST", "").strip()
    
    if not smtp_port:
        try:
            smtp_port = int(os.environ.get("SMTP_PORT", 0))
        except Exception:
            smtp_port = 0

    # Auto-detect host and port based on sender email if omitted
    if not smtp_host:
        if sender_email.lower().endswith("@gmail.com"):
            smtp_host = "smtp.gmail.com"
            if not smtp_port:
                smtp_port = 587
        elif any(sender_email.lower().endswith(d) for d in ("@outlook.com", "@hotmail.com", "@live.com")):
            smtp_host = "smtp-mail.outlook.com"
            if not smtp_port:
                smtp_port = 587
        elif sender_email.lower().endswith("@yahoo.com"):
            smtp_host = "smtp.mail.yahoo.com"
            if not smtp_port:
                smtp_port = 465
        else:
            smtp_host = "smtp.hostinger.com"

    if not smtp_port:
        smtp_port = 465 if "hostinger" in smtp_host or "yahoo" in smtp_host else 587

    if not sender_email or not sender_password:
        return {
            "success": False,
            "error": "Missing credentials. Please enter Sender Email and Password, or configure .env file."
        }

    target_email = test_recipient or "test@algoryx.in"

    # Brevo API Key check
    if sender_password.startswith("xkeysib-"):
        res = _send_via_brevo_api(sender_password, sender_email, target_email, "⚡ SMTP Test - Connection & Delivery Verified", f"This is an automated test email sent to {target_email} from PDF Editor engine.", "")
        if res.get("success"):
            return {"success": True, "message": f"Successfully authenticated & dispatched test email to {target_email} via Brevo HTTP API!"}
        else:
            return {"success": False, "error": res.get("error")}

    # Standard SMTP
    ports_to_try = [int(smtp_port)]
    alt_port = 587 if int(smtp_port) == 465 else 465
    if alt_port not in ports_to_try:
        ports_to_try.append(alt_port)

    last_error = ""
    for port in ports_to_try:
        try:
            server = _connect_smtp(smtp_host, port, timeout=20)
            server.login(sender_email, sender_password)

            # Send actual test email to target_email
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = target_email
            msg["Subject"] = "⚡ SMTP Test Email - Connection Verified"
            msg.attach(MIMEText(
                f"Hello,\n\n"
                f"This is an automated SMTP test email dispatched by the PDF Editor Engine.\n\n"
                f"Sender: {sender_email}\n"
                f"Recipient: {target_email}\n"
                f"Host: {smtp_host}:{port}\n"
                f"Status: Connection, Authentication, and Email Dispatch Succeeded!\n\n"
                f"Best Regards,\nHR Team",
                "plain"
            ))
            server.send_message(msg)
            server.quit()

            return {
                "success": True,
                "message": f"Successfully connected & sent test email to {target_email} via {smtp_host}:{port}!"
            }
        except Exception as e:
            err_msg = str(e)
            formatted = _format_auth_error(err_msg, smtp_host, sender_email)
            if "535" in err_msg or "authentication failed" in err_msg.lower():
                return {"success": False, "error": formatted}
            last_error = formatted


    return {
        "success": False,
        "error": last_error or f"SMTP Connection Failed ({smtp_host}): Unknown error."
    }


def send_email_with_attachment(
    to_email: str,
    subject: str,
    body_text: str,
    attachment_path: Optional[str] = None,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    sender_email: Optional[str] = None,
    sender_password: Optional[str] = None,
    attachment_pdf_path: Optional[str] = None
) -> Dict[str, Any]:
    """Sends an individual automated email with attached document/image (PDF, JPEG, PNG) to recipient."""
    load_dotenv_if_exists()

    if not attachment_path and attachment_pdf_path:
        attachment_path = attachment_pdf_path

    if sender_email is None:
        sender_email = os.environ.get("SMTP_SENDER_EMAIL", "").strip()
    else:
        sender_email = sender_email.strip()

    if sender_password is None:
        sender_password = os.environ.get("SMTP_SENDER_PASSWORD", "").strip()
    else:
        sender_password = sender_password.strip()

    if not smtp_host:
        smtp_host = os.environ.get("SMTP_HOST", "smtp.hostinger.com").strip()
    
    if not smtp_port:
        try:
            smtp_port = int(os.environ.get("SMTP_PORT", 0))
        except Exception:
            smtp_port = 0
    if not smtp_port:
        smtp_port = 465 if "hostinger" in smtp_host.lower() else 587

    if not sender_email or not sender_password:
        return {
            "success": False,
            "error": "Missing SMTP sender credentials. Please configure sender email and password.",
            "recipient": to_email
        }


    # Brevo HTTP API dispatch if API key supplied
    if sender_password.startswith("xkeysib-"):
        return _send_via_brevo_api(sender_password, sender_email, to_email, subject, body_text, attachment_path)

    # Standard SMTP dispatch
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))

    if attachment_path and os.path.exists(attachment_path):
        filename = os.path.basename(attachment_path)
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=filename)
            part['Content-Disposition'] = f'attachment; filename="{filename}"'
            msg.attach(part)

    ports_to_try = [int(smtp_port)]
    alt_port = 587 if int(smtp_port) == 465 else 465
    if alt_port not in ports_to_try:
        ports_to_try.append(alt_port)

    last_err = ""
    for port in ports_to_try:
        try:
            server = _connect_smtp(smtp_host, port, timeout=25)
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            return {"success": True, "recipient": to_email}
        except Exception as e:
            err_str = str(e)
            formatted = _format_auth_error(err_str, smtp_host, sender_email)
            if "535" in err_str or "authentication failed" in err_str.lower():
                return {
                    "success": False,
                    "error": formatted,
                    "recipient": to_email
                }
            last_err = formatted

    return {
        "success": False,
        "error": last_err or f"SMTP Dispatch Error ({smtp_host})",
        "recipient": to_email
    }


# Backward-compatibility alias for PDF sender
send_email_with_pdf_attachment = send_email_with_attachment



class SMTPBatchSender:
    """Reuses an active SMTP connection across multiple emails in bulk operations for speed and rate-limit prevention."""

    def __init__(self, host: str, port: int, sender_email: str, sender_password: str):
        self.host = host
        self.port = int(port)
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.server: Optional[smtplib.SMTP] = None
        self.is_api = sender_password.startswith("xkeysib-")

    def connect(self) -> Dict[str, Any]:
        """Pre-flight connection and authentication test."""
        if self.is_api:
            return test_smtp_connection(self.host, self.port, self.sender_email, self.sender_password)

        ports_to_try = [self.port]
        alt_port = 587 if self.port == 465 else 465
        if alt_port not in ports_to_try:
            ports_to_try.append(alt_port)

        last_error = ""
        for p in ports_to_try:
            try:
                server = _connect_smtp(self.host, p, timeout=20)
                server.login(self.sender_email, self.sender_password)
                self.server = server
                self.port = p
                return {"success": True, "message": f"Connected to {self.host}:{p}"}
            except Exception as e:
                err_str = str(e)
                last_error = _format_auth_error(err_str, self.host, self.sender_email)
                if "535" in err_str or "authentication failed" in err_str.lower():
                    break

        return {"success": False, "error": last_error or "SMTP Connection Failed"}

    def send_one(self, to_email: str, subject: str, body_text: str, pdf_path: str) -> Dict[str, Any]:
        """Dispatches an email through active session or API."""
        if self.is_api:
            return send_email_with_pdf_attachment(
                to_email=to_email,
                subject=subject,
                body_text=body_text,
                attachment_pdf_path=pdf_path,
                smtp_host=self.host,
                smtp_port=self.port,
                sender_email=self.sender_email,
                sender_password=self.sender_password
            )

        if not self.server:
            conn_res = self.connect()
            if not conn_res.get("success"):
                return {"success": False, "error": conn_res.get("error", "SMTP not connected"), "recipient": to_email}

        msg = MIMEMultipart()
        msg["From"] = self.sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))

        if pdf_path and os.path.exists(pdf_path):
            filename = os.path.basename(pdf_path)
            with open(pdf_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=filename)
                part['Content-Disposition'] = f'attachment; filename="{filename}"'
                msg.attach(part)

        try:
            self.server.send_message(msg)
            return {"success": True, "recipient": to_email}
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPSenderRefused, socket.error):
            # Session expired or disconnected, attempt one reconnect
            try:
                self.close()
                conn_res = self.connect()
                if conn_res.get("success") and self.server:
                    self.server.send_message(msg)
                    return {"success": True, "recipient": to_email}
            except Exception as e:
                return {"success": False, "error": f"Send failed after reconnect: {str(e)}", "recipient": to_email}
        except Exception as e:
            return {"success": False, "error": str(e), "recipient": to_email}

    def close(self) -> None:
        """Closes the underlying SMTP connection safely."""
        if self.server:
            try:
                self.server.quit()
            except Exception:
                pass
            self.server = None
