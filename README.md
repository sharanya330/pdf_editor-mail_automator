# pdf_editor-mail_automator
# PDF Editor Mail Automator

This project is a Python-based mail automation service designed to dispatch emails with file attachments. It uses the Brevo HTTP API for reliable email delivery and provides an API endpoint for easy integration.

## Features
- Sends emails with document/image attachments (PDF, JPEG, PNG)
- Integrates with Brevo HTTP API for email dispatch
- Simple REST API for sending emails
- Environment variable support for configuration

## Prerequisites
- Python 3.7+
- Brevo API Key (`SMTP_SENDER_PASSWORD`)
- Verified sender email (`SMTP_SENDER_EMAIL`)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd pdf-editor-mail_automator
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Create a `.env` file in the root directory with the following variables:

```env
PORT=8001
SMTP_SENDER_EMAIL=your-verified-email@example.com
SMTP_SENDER_PASSWORD=your-brevo-api-key
SMTP_HOST=smtp.brevo.com
SMTP_PORT=587
```

## Usage

### Run the Server

```bash
python pdf/main.py
```

The server will start on the port specified in the environment (default: 8001).

### API Documentation

#### Send Email

**Endpoint:** `/send_email`

**Method:** `POST`

**Request Body:**
```json
{
  "to": "[EMAIL_ADDRESS]",
  "subject": "Test Email",
  "body_text": "This is a test email.",
  "attachment_path": "/path/to/your/file.pdf"
}
```

**Response:**
```json
{
  "status": "success",
  "result": {
    "message": "Email sent successfully",
    "recipient": "[EMAIL_ADDRESS]"
  }
}
```

## Development

The project uses the `fastapi` framework and `requests` library for the HTTP API.

### Running Tests

Add test cases in `tests/test_email.py` and run:

```bash
python -m pytest tests/
```

## License

MIT License
