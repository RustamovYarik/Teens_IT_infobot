import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite

API_TOKEN = '7940830818:AAG5-S_vrp_qdyuULVgMFPBJzClZYTIV_c4'
ADMIN_ID = 1266484724
DB_PATH = "videos.db"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                caption TEXT NOT NULL,
                media_type TEXT DEFAULT 'video',
                sent BOOLEAN DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_send', '1')")
        await db.commit()


async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
        await db.commit()

    welcome_id = await get_setting("welcome_video_id")
    welcome_caption = await get_setting("welcome_caption") or "Welcome to the bot!"
    media_type = await get_setting("welcome_media_type") or "video"

    if welcome_id:
        if media_type == "photo":
            await message.answer_photo(welcome_id, caption=welcome_caption, parse_mode=ParseMode.HTML)
        else:
            await message.answer_video(welcome_id, caption=welcome_caption, parse_mode=ParseMode.HTML)
    else:
        await message.answer("Welcome! (no welcome media set yet)")


@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="Set Welcome Media", callback_data="set_welcome")
    builder.button(text="Send Content Media", callback_data="add_content")
    builder.button(text="Delete Content Media", callback_data="delete_content")
    builder.button(text="User Count", callback_data="user_count")
    builder.button(text="Toggle Auto Send", callback_data="toggle_auto")
    builder.button(text="List All Media", callback_data="list_all_media")

    await message.answer("Admin Panel:", reply_markup=builder.as_markup())


@dp.callback_query(F.data == "set_welcome")
async def handle_set_welcome(call: CallbackQuery):
    await call.message.answer("Please send the video or photo you want to set as welcome media with a caption.")
    await set_setting("awaiting_welcome", "1")
    await call.answer()


@dp.callback_query(F.data == "add_content")
async def handle_add_content(call: CallbackQuery):
    await call.message.answer("Please send the video or photo you want to add as content media with a caption.")
    await set_setting("awaiting_welcome", "0")
    await call.answer()


@dp.callback_query(F.data == "delete_content")
async def handle_delete_content(call: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, caption FROM videos ORDER BY id DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await call.message.answer("No content media found.")
        await call.answer()
        return

    builder = InlineKeyboardBuilder()
    for row in rows:
        short_caption = (row[1][:30] + "...") if len(row[1]) > 30 else row[1]
        builder.button(text=f"🗑 {short_caption}", callback_data=f"delete_{row[0]}")
    await call.message.answer("Select a media to delete:", reply_markup=builder.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("delete_"))
async def handle_individual_delete(call: CallbackQuery):
    media_id = int(call.data.replace("delete_", ""))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM videos WHERE id = ?", (media_id,))
        await db.commit()
    await call.message.answer("Media deleted successfully.")
    await call.answer()


@dp.callback_query(F.data == "list_all_media")
async def handle_list_all_media(call: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, caption FROM videos ORDER BY id DESC") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await call.message.answer("No media in the database.")
        return

    builder = InlineKeyboardBuilder()
    for row in rows:
        short_caption = (row[1][:30] + "...") if len(row[1]) > 30 else row[1]
        builder.button(text=f"▶ {short_caption}", callback_data=f"view_{row[0]}")
    await call.message.answer("All content media:", reply_markup=builder.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("view_"))
async def handle_view_media(call: CallbackQuery):
    media_id = int(call.data.replace("view_", ""))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT file_id, caption, media_type FROM videos WHERE id = ?", (media_id,)) as cursor:
            row = await cursor.fetchone()

    if not row:
        await call.message.answer("Media not found.")
        return

    if row[2] == "photo":
        await call.message.answer_photo(row[0], caption=row[1], parse_mode=ParseMode.HTML)
    else:
        await call.message.answer_video(row[0], caption=row[1], parse_mode=ParseMode.HTML)

    await call.answer()


@dp.callback_query(F.data == "user_count")
async def handle_user_count(call: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            count = (await cursor.fetchone())[0]
    await call.message.answer(f"Total users: {count}")
    await call.answer()


@dp.callback_query(F.data == "toggle_auto")
async def toggle_auto(call: CallbackQuery):
    current = await get_setting("auto_send")
    new_value = "0" if current == "1" else "1"
    await set_setting("auto_send", new_value)
    status = "enabled" if new_value == "1" else "disabled"
    await call.message.answer(f"Auto sending is now {status}.")
    await call.answer()


@dp.message(F.video | F.photo)
async def handle_media_message(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    waiting = await get_setting("awaiting_welcome")

    file_id = (
        message.video.file_id if message.video
        else message.photo[-1].file_id if message.photo
        else None
    )
    caption = message.caption or ""

    if not file_id:
        await message.reply("Unsupported media type.")
        return

    media_type = "video" if message.video else "photo"

    if waiting == "1":
        await set_setting("welcome_video_id", file_id)
        await set_setting("welcome_caption", caption)
        await set_setting("welcome_media_type", media_type)
        await set_setting("awaiting_welcome", "0")
        await message.reply("Welcome media updated!")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO videos (file_id, caption, media_type) VALUES (?, ?, ?)",
            (file_id, caption, media_type)
        )
        await db.commit()

    await message.reply("Media saved and will be sent to users.")


async def send_unsent_videos():
    print("✅ Background sender started")
    while True:
        auto_send = await get_setting("auto_send")
        if auto_send != "1":
            await asyncio.sleep(10)
            continue

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id, file_id, caption, media_type FROM videos WHERE sent = 0") as cursor:
                videos = await cursor.fetchall()

            async with db.execute("SELECT id FROM users") as cursor:
                user_ids = [row[0] for row in await cursor.fetchall()]

            for vid in videos:
                for uid in user_ids:
                    try:
                        if vid[3] == "photo":
                            await bot.send_photo(uid, vid[1], caption=vid[2], parse_mode=ParseMode.HTML)
                        else:
                            await bot.send_video(uid, vid[1], caption=vid[2], parse_mode=ParseMode.HTML)
                    except Exception as e:
                        print(f"Error sending to {uid}: {e}")
                await db.execute("UPDATE videos SET sent = 1 WHERE id = ?", (vid[0],))
                await db.commit()

        await asyncio.sleep(10)


async def main():
    await init_db()
    asyncio.create_task(send_unsent_videos())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
