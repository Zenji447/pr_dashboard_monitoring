#!/home/zen6/.venvs/google-sheets/bin/python
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import json

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
CREDS_PATH = Path('/home/zen6/.openclaw/credentials/google-oauth-client.json')
TOKEN_PATH = Path('/home/zen6/.openclaw/state/google/google-sheets-token.json')
SHEET_ID = '1Sm_yOJvHMaPMvT1tqTH2NtYVhg62_6RERrTVvfcxACY'
RANGE = 'B2C Pull Request to Review - DevOps Team'


def get_credentials():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def main():
    if not CREDS_PATH.exists():
        raise SystemExit(f'No encuentro credenciales OAuth en {CREDS_PATH}')
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    meta = sheet.get(spreadsheetId=SHEET_ID).execute()
    print('SPREADSHEET:', meta.get('properties', {}).get('title'))
    tabs = [s.get('properties', {}).get('title') for s in meta.get('sheets', [])]
    print('TABS:', json.dumps(tabs, ensure_ascii=False))
    values = sheet.values().get(spreadsheetId=SHEET_ID, range=RANGE).execute().get('values', [])
    print('ROWS:', len(values))
    for row in values[:10]:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == '__main__':
    main()
