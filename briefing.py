"""Morning briefing — today's calendar and unread email via Google APIs.

One-time setup (on your computer):
1. In Google Cloud Console, create an OAuth "Desktop app" client and
   download its JSON (see README).
2. Save it next to this file as `credentials.json` (gitignored).
3. The first briefing opens a browser — sign in and click Allow. The
   resulting token is cached in `token.json` (also gitignored) and
   refreshes itself; you won't be asked again.

Access is read-only (gmail.readonly + calendar.readonly) and revocable
any time at https://myaccount.google.com/permissions
"""

from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
CREDENTIALS = ROOT / "credentials.json"
TOKEN = ROOT / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _get_creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN.write_text(creds.to_json())
    return creds


def _header(msg: dict, name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def build_briefing() -> tuple[str, bool]:
    """Return (briefing_text, is_error)."""
    if not CREDENTIALS.exists():
        return (
            "Google isn't connected yet. Download the OAuth Desktop-app JSON "
            "from console.cloud.google.com and save it next to esi.py as "
            "credentials.json, then ask for the briefing again.",
            True,
        )
    try:
        from googleapiclient.discovery import build
    except ImportError:
        return "Google libraries missing — run: pip install -r requirements.txt", True

    try:
        creds = _get_creds()
        lines = [f"Briefing for {datetime.now().strftime('%A, %B %d')}."]

        # Today's calendar
        cal = build("calendar", "v3", credentials=creds)
        now = datetime.now().astimezone()
        end = now.replace(hour=23, minute=59, second=59)
        events = cal.events().list(
            calendarId="primary", timeMin=now.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=10,
        ).execute().get("items", [])
        if events:
            lines.append(f"\nCalendar — {len(events)} remaining today:")
            for ev in events:
                start = ev["start"].get("dateTime", ev["start"].get("date", ""))
                when = start[11:16] if "T" in start else "all day"
                lines.append(f"- {when}: {ev.get('summary', '(no title)')}")
        else:
            lines.append("\nCalendar: nothing else scheduled today.")

        # Unread email (last day)
        gmail = build("gmail", "v1", credentials=creds)
        refs = gmail.users().messages().list(
            userId="me", q="is:unread newer_than:1d", maxResults=8,
        ).execute().get("messages", [])
        if refs:
            lines.append(f"\nUnread email — {len(refs)} in the last day:")
            for ref in refs:
                msg = gmail.users().messages().get(
                    userId="me", id=ref["id"], format="metadata",
                    metadataHeaders=["From", "Subject"],
                ).execute()
                sender = _header(msg, "From").split("<")[0].strip().strip('"')
                lines.append(f"- {sender}: {_header(msg, 'Subject')}")
        else:
            lines.append("\nInbox: no unread mail in the last day. Clean slate.")

        return "\n".join(lines), False
    except Exception as exc:
        return f"Briefing failed: {exc}", True
