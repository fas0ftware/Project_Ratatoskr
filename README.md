# Ratatoskr

Sends a WhatsApp Web message to a contact with Selenium, using a dedicated Chrome profile so your normal Chrome and the WhatsApp login are kept separate.

## Setup

```bash
pip install -r requirements.txt     # selenium, webdriver-manager
```

Needs Google Chrome. The matching driver is downloaded by `webdriver-manager`.

## Usage

```bash
python main.py "Contact name" "Message text"
python main.py "Contact name" "Message text" --repeat 3 --login-wait 45
```

- The contact name must match the chat as shown in WhatsApp.
- On the first run scan the QR code in the window that opens (`--login-wait` is how long the script waits). The session is stored in `~/.ratatoskr_profile` (override with `--profile` or `RATATOSKR_PROFILE`), so later runs usually need no scan.
- `--repeat` is capped at 20 to avoid spamming.

## Tests

```bash
python -m unittest discover -v
```

Only the command-line handling is tested; the browser part needs Chrome and a WhatsApp account. `tools/smoke_whatsapp_web.py` opens WhatsApp Web without a profile to check that Selenium works.

## Limitations

- Automating WhatsApp Web is against WhatsApp's terms of use and your account can be blocked. For anything serious use the official WhatsApp Business API.
- Selectors (`data-tab` values) depend on WhatsApp's page layout and may break at any time.
- The profile folder holds your logged-in WhatsApp session: keep it private and never commit it.
