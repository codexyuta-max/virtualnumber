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

### Telegram user confirmation endpoint

A helper endpoint lets the bot verify and notify a Telegram user ID.  Call it like:
3333333333
```
GET /id=<telegram-user-id>
```

If the ID exists in the `allow_user` collection the server will send a simple
confirmation message directly to that chat via the configured bot token.
Otherwise the request returns a 403 and nothing is sent.

## Notes
- This is for educational purposes only.
- IP addresses are not intentionally stored by the app.
