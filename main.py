import pandas as pd
import random
import sqlite3
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InputFile
import os
from aiogram.types.web_app_info import WebAppInfo
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram import Bot, Dispatcher, executor, types
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = '7002609477:AAHnGqWiJ0IYvusj--Ujm0GUjU0kbQFRK4Y'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

contact_list = []
phones = {}
CHANNEL_ID = -1001449241974
welcome_text = "Дарим за подписку пушечный промокод, который можно использовать на нашем сайте."
subscribed_users = {}

class PromoCodeStates(StatesGroup):
    DELETE_PROMO_CODE = State()
    ADD_PROMO_CODE = State()

issued_promo_codes = {}
promo_codes = []

def create_excel_file(data):
    df = pd.DataFrame(data, columns=["id", "phone"])
    df.to_excel("users_data.xlsx", index=False)

def fetch_data_from_db():
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()
    
    # Создаем таблицу если не существует
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            phone TEXT
        )
    ''')
    
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    connection.close()
    return rows

@dp.message_handler(commands=['show'])
async def show_data(message: types.Message):
    data = fetch_data_from_db()
    create_excel_file(data)
    await message.answer_document(document=open("users_data.xlsx", 'rb'))

def create_connection():
    connection = None
    try:
        connection = sqlite3.connect('users.db')
        cursor = connection.cursor()
        # Создаем таблицу если не существует
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                phone TEXT
            )
        ''')
        connection.commit()
        print("Connection to SQLite DB successful")
    except sqlite3.Error as e:
        print(f"The error '{e}' occurred")
    return connection

def add_user(connection, user_id):
    try:
        cursor = connection.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (id)
            VALUES (?)
        ''', (user_id,))
        connection.commit()
        print("User added successfully")
    except sqlite3.Error as e:
        print(f"The error '{e}' occurred")

async def check_membership(user_id):
    subscribed = await is_user_subscribed(user_id)
    admin_or_owner = await is_user_admin_or_owner(user_id)
    return subscribed or admin_or_owner

async def is_user_subscribed(user_id):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f'https://api.telegram.org/bot{API_TOKEN}/getChatMember',
            json={'chat_id': CHANNEL_ID, 'user_id': user_id}
        ) as response:
            data = await response.json()
            if response.status == 200:
                return data['result']['status'] == 'member'
            else:
                return False

async def is_user_admin_or_owner(user_id):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f'https://api.telegram.org/bot{API_TOKEN}/getChatMember',
            json={'chat_id': CHANNEL_ID, 'user_id': user_id}
        ) as response:
            data = await response.json()
            if response.status == 200:
                status = data['result']['status']
                return status in ['creator', 'administrator']
            else:
                return False

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    print(f"User {user_id} started the bot.")

    connection = create_connection()
    add_user(connection, user_id)
    connection.close()

    is_subscribed = await check_membership(user_id)

    if is_subscribed:
        print(f"User {user_id} is subscribed.")
        keyboard = InlineKeyboardMarkup(row_width=2)
        subscribe_button = InlineKeyboardButton(text="Подписаться", url="t.me/off_street")
        get_code_button = InlineKeyboardButton(text="Получить промокод", callback_data="get_code")
        web_app = InlineKeyboardButton('ОФОРМИТЬ ЗАКАЗ', web_app=WebAppInfo(url='https://offstreet.online/'))
        get_contact = InlineKeyboardButton(text="Поделиться контактом", callback_data="get_contact")
        keyboard.add(subscribe_button, get_code_button, get_contact, web_app)
        photo_path = "main.jpeg"
        await message.answer_photo(
            photo=InputFile(os.path.abspath(photo_path)),
            caption=f"С Возвращением в OFF STREET, {user_name}!🔥\n- - - - - -\n{welcome_text}\n- - - - - -\nЖми получить промокод",
            reply_markup=keyboard
        )
    else:
        print(f"User {user_id} is not subscribed.")
        keyboard = InlineKeyboardMarkup()
        subscribe_button = InlineKeyboardButton(text="Подписаться", url="t.me/off_street")
        keyboard.add(subscribe_button)
        photo_path = "main.jpeg"
        await message.answer_photo(
            photo=InputFile(os.path.abspath(photo_path)),
            caption=f"Добро пожаловать в OFF STREET, {user_name}!🔥\n- - - - - -\n{welcome_text}\n- - - - - -\nЧтобы получить промокод, подпишитесь на канал по кнопке ниже и снова нажмите /start",
            reply_markup=keyboard
        )

@dp.callback_query_handler(lambda query: query.data == 'get_contact')
async def get_contact(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('Поделиться контактом', request_contact=True))
    await bot.send_message(user_id, 'Для продолжения нажмите кнопку «ПОДЕЛИТЬСЯ КОНТАКТОМ», и получите от нас промокод в подарок!👇', reply_markup=markup)

@dp.message_handler(content_types=types.ContentType.CONTACT)
async def contact_received(message: types.Message):
    user_id = message.from_user.id
    phone_number = message.contact.phone_number

    connection = create_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('''
            UPDATE users
            SET phone = ?
            WHERE id = ?
        ''', (phone_number, user_id))
        connection.commit()
        print(f"Phone number added for user {user_id}")
        await message.answer("Ваш номер телефона успешно сохранен.")
    except sqlite3.Error as e:
        print(f"The error '{e}' occurred")
    connection.close()

@dp.message_handler(commands=['post'])
async def send_message_to_all(message: types.Message):
    text_to_send = message.text.replace("/post", "").strip()
    connection = create_connection()

    try:
        cursor = connection.cursor()
        cursor.execute('SELECT id FROM users')
        user_ids = cursor.fetchall()

        for user_id in user_ids:
            try:
                await bot.send_message(user_id[0], text_to_send)
                print(f"Message sent to user {user_id[0]}")
            except Exception as e:
                print(f"Failed to send message to user {user_id[0]}. Error: {e}")

        print("Message sent to all users")
    except sqlite3.Error as e:
        print(f"The error '{e}' occurred")
    connection.close()

@dp.message_handler(commands=['rm'])
async def change_welcome_text(message: types.Message):
    global welcome_text
    allowed_users = [5429082466, 713476634, 832507232]
    if message.from_user.id in allowed_users:
        new_text = message.text.split('/rm', 1)[-1].strip()
        welcome_text = new_text
        print("Текст приветствия успешно изменен:", welcome_text)
        await message.answer("Текст приветствия успешно изменен.")
    else:
        await message.answer("У вас нет прав для выполнения этой команды.")

@dp.message_handler(commands=['code'])
async def code(message: types.Message):
    allowed_users = [5429082466, 713476634, 832507232]
    user_id = message.from_user.id
    if user_id in allowed_users:
        if promo_codes:
            promo_codes_list = "\n".join([f"{index + 1}. {code}" for index, code in enumerate(promo_codes)])
            await message.answer(
                f"Список доступных промокодов:\n{promo_codes_list}\n\nЧто вы хотите сделать?",
                reply_markup=InlineKeyboardMarkup().row(
                    InlineKeyboardButton("Добавить промокод", callback_data="add_code"),
                    InlineKeyboardButton("Удалить промокод", callback_data="delete_code")
                )
            )
        else:
            await message.answer("Список доступных промокодов пуст.\n\nЧто вы хотите сделать?",
                                 reply_markup=InlineKeyboardMarkup().row(
                                     InlineKeyboardButton("Добавить промокод", callback_data="add_code")
                                 ))
    else:
        await message.answer("Извините, у вас нет доступа к этой функции.")

def add_promo_code(code):
    promo_codes.append(code)

@dp.callback_query_handler(lambda c: c.data == 'get_code')
async def get_code(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_name = callback_query.from_user.first_name
    if promo_codes:
        if user_id in issued_promo_codes:
            await callback_query.message.answer(f"Твой промокод: {issued_promo_codes[user_id]}")
        else:
            random_promo_code = random.choice(promo_codes)
            issued_promo_codes[user_id] = random_promo_code
            await callback_query.message.answer(f"Твой промокод: {random_promo_code}")
    else:
        await callback_query.message.answer("Промокодов в данный момент нет.")

@dp.message_handler(content_types=['new_chat_members'])
async def on_new_chat_members(message: types.Message):
    for user in message.new_chat_members:
        if user.id == bot.id:
            subscribed_users[message.chat.id] = True
            logging.info(f"Бот был добавлен в паблик {message.chat.title}")

@dp.callback_query_handler(lambda c: c.data == 'delete_code')
async def delete_code(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Введите индексы промокодов, которые нужно удалить (через пробел или запятую):")
    await PromoCodeStates.DELETE_PROMO_CODE.set()

@dp.message_handler(state=PromoCodeStates.DELETE_PROMO_CODE)
async def process_delete_promo_code(message: types.Message, state: FSMContext):
    indexes_str = message.text
    indexes = []
    try:
        indexes = [int(index.strip()) for index in indexes_str.replace(',', ' ').split()]
    except ValueError:
        await message.answer("Некорректный ввод. Пожалуйста, введите индексы числами, разделенными пробелом или запятой.")
        return

    if any(index < 1 or index > len(promo_codes) for index in indexes):
        await message.answer("Некорректные индексы. Пожалуйста, выберите индексы из списка.")
        return

    deleted_promo_codes = [promo_codes.pop(index - 1) for index in sorted(indexes, reverse=True)]
    await state.finish()

    deleted_promo_codes_str = '\n'.join(deleted_promo_codes)
    await message.answer(f"Промокоды успешно удалены:\n{deleted_promo_codes_str}")

@dp.callback_query_handler(lambda c: c.data == 'add_code')
async def add_code(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Введите новый промокод:")
    await PromoCodeStates.ADD_PROMO_CODE.set()

@dp.message_handler(state=PromoCodeStates.ADD_PROMO_CODE)
async def process_add_promo_code(message: types.Message, state: FSMContext):
    new_code = message.text
    add_promo_code(new_code)
    await state.finish()
    await message.answer("Новый промокод успешно добавлен!")

if __name__ == '__main__':
    executor.start_polling(dp)
