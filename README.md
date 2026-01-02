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
