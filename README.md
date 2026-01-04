# BroBot on Railway (Docker, Python 3.11)

## Required Railway Variables
Set these in **Service → Variables**:

- BOT_TOKEN: Telegram bot token from BotFather (or use TOKEN)
- SUPER_ADMIN_ID: Your Telegram numeric user ID (digits only)
- DATA_DIR: data
- REQUIRED_CHANNEL: @broichancy (optional)

After adding variables, Redeploy/Restart the service.

## Notes
- This project includes a Dockerfile to pin Python 3.11 (avoids Python 3.13 `imghdr` issues).
- Data is stored as JSON files inside `DATA_DIR`. For persistence on Railway, add a Volume and mount it to `/app/data`.
## New Features (vNext)
- Referrals: each new user via referral link grants **10 points**; redeem **100 points → 10000** added to bot balance.
- iChancy Pool: pre-created accounts can be added in bulk from Admin Panel → **🗂 مخزون إيـشانسي**.
  - Format (one per line): `username:password`
  - Users choose only the **username**; password is auto-delivered with copy buttons.
- Copy helpers: credentials are sent in code blocks + buttons to receive a short copy-friendly message.

## Data Files
These files will be created inside `/app/data`:
- eishancy_pool.json (pool accounts)
- referrals.json (referral bookkeeping)

