import asyncio
import requests
import streamlit as st
import logging
import feedparser
import random
import threading
from datetime import datetime, timedelta
from aiogram import Bot

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- КОНФИГУРАЦИЯ ---
TOKEN = st.secrets.get("NEWS_BOT_TOKEN")
OR_KEY = st.secrets.get("OPENROUTER_API_KEY")
CHANNEL_ID = "@info_sphere_tg" 

bot = Bot(token=TOKEN)

RSS_SOURCES = [
    "https://news.google.com/rss/search?q=Ukraine+war+politics+economy+world&hl=ru&gl=UA&ceid=UA:ru",
    "https://www.unian.net/rss",
    "https://censor.net/includes/news_ru.xml",
    "https://nv.ua/rss/all.xml",
    "https://www.bbc.co.uk/news/world/rss.xml"
]

EXCLUDE_WORDS = ['гороскоп', 'диета', 'георгин', 'кожа', 'цветы', 'рецепт', 'шоу-биз', 'бритни спирс']

posted_links = set()
last_topics = []

async def rewrite_news_ai(title, desc):
    """ИИ превращает новость в пост. Используем Gemini Flash (бесплатная)"""
    # Если эта модель будет выдавать ошибку, попробуй "mistralai/mistral-7b-instruct:free"
    model_name = "google/gemini-2.0-flash-exp:free"
    
    prompt = (
        f"Напиши вирусный аналитический пост для Телеграм.\n"
        f"НОВОСТЬ: {title}. {desc}\n\n"
        f"ИНСТРУКЦИЯ: Глобальный дерзкий стиль, капс в заголовке, провокация в конце. До 600 символов."
    )
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OR_KEY}",
                "HTTP-Referer": "https://streamlit.io",
                "Content-Type": "application/json"
            },
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        
        result = response.json()
        
        # ЛОГИРУЕМ ОШИБКУ ОТ API, ЕСЛИ ОНА ЕСТЬ
        if "error" in result:
            logging.error(f"OpenRouter API Error: {result['error'].get('message')}")
            return None
            
        return result['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Ошибка OpenRouter: {e}")
        return None

async def post_engine():
    logging.info("!!! МОНИТОРИНГ ЗАПУЩЕН !!!")
    while True:
        try:
            logging.info("--- Сканирую RSS источники ---")
            all_entries = []
            for url in RSS_SOURCES:
                feed = feedparser.parse(url)
                all_entries.extend(feed.entries)
            
            random.shuffle(all_entries)

            for entry in all_entries:
                if entry.link in posted_links:
                    continue
                
                logging.info(f"Обработка: {entry.title[:50]}...")
                viral_text = await rewrite_news_ai(entry.title, getattr(entry, 'description', ''))
                
                if viral_text:
                    final_post = f"{viral_text}\n\n<a href='{entry.link}'>🔗 Источник</a>"
                    await bot.send_message(chat_id=CHANNEL_ID, text=final_post, parse_mode="HTML")
                    posted_links.add(entry.link)
                    logging.info("✅ ПОСТ ОПУБЛИКОВАН. Сон 15 минут.")
                    await asyncio.sleep(900)
                    break
            else:
                logging.info("Новых новостей нет, жду 5 минут.")
                await asyncio.sleep(300)
                
        except Exception as e:
            logging.error(f"Ошибка в цикле: {e}")
            await asyncio.sleep(60)

def run_async_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(post_engine())

# --- ИНТЕРФЕЙС STREAMLIT ---
st.set_page_config(page_title="News AI Bot", page_icon="🗞")
st.title("🗞 Редакция Info Sphere AI")

if "bot_started" not in st.session_state:
    st.session_state.bot_started = True
    threading.Thread(target=run_async_bot, daemon=True).start()
    st.success("🤖 Бот запущен в фоновом потоке!")
else:
    st.info("✅ Бот работает. Проверь логи Streamlit Cloud для деталей.")
