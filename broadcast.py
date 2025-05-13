from aiohttp import web, FormData
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dotenv import dotenv_values
import aiohttp
import sys

config = dotenv_values(".env")

PASSCODE = config.get('PASSCODE')
API_TOKEN = config.get('BOT_TOKEN')
BACKEND_URL = config.get('BACKEND_URL')
WEBHOOK_PATH = '/webhook'
WEBHOOK_SECRET = config.get('WEBHOOK_SECRET')  # Optional
BASE_WEBHOOK_URL = config.get('WEBHOOK_URL') # Replace with your actual domain or ngrok URL

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# 💾 save groups

@router.message(CommandStart())
async def saveGroup(message: Message):
    if message.chat.type in ['group', 'supergroup']:
        async with aiohttp.ClientSession() as session:

            # see if group already exists
            async with session.get(f'{BACKEND_URL}/api/telegram-groups/?passcode={PASSCODE}') as resp:
                data = await resp.json()
                for group in data:
                    if group['group_id'] == str(message.chat.id):
                        # group already exists
                        return
            
            # save the group
            group = message.chat
            payload = FormData()
            payload.add_field("title", group.title)
            payload.add_field("group_id", str(group.id))

            url = f'{BACKEND_URL}/api/telegram-groups/?passcode={PASSCODE}'
            async with session.post(url, data=payload) as resp:
                return resp.status >= 200 and resp.status < 300
    return False

# 📨 send messages to groups

async def send_message_to_group(request):
    if PASSCODE == request.query.get('passcode'):
        group_id = request.query.get('group')
        message = request.query.get('message')
        if not group_id or not message:
            return web.json_response({"ok": False, "reason": "Missing 'group' or 'message' parameter"}, status=400)

        try:
            await bot.send_message(chat_id=int(group_id), text=message)
            return web.json_response({"ok": True, "message": "Message sent"})
        except Exception as e:
            return web.json_response({"ok": False}, status=500)
        
    else:
        return web.json_response({'ok':False}, status=400)

# 🌐 creating and removing webhooks

async def on_startup(app: web.Application):
    await bot.set_webhook(
        url=f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}",
        secret_token=WEBHOOK_SECRET
    )

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()

app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

app.router.add_get("/send", send_message_to_group)

# Setup the webhook handler
SimpleRequestHandler(
    dispatcher=dp,
    bot=bot,
    secret_token=WEBHOOK_SECRET
).register(app, path=WEBHOOK_PATH)

try:
    port = int(sys.argv[ sys.argv.index('-p') + 1 ])
except:
    print("Port was not defined properly, set it as \"-p PORT\"")
    sys.exit(1)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=port)
