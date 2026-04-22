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

EXCLUDE_WORDS = [
    'гороскоп', 'диета', 'георгин', 'кожа', 'цветы', 'рецепт', 
    'шоу-биз', 'бритни спирс', 'похудеть', 'сад', 'огород'
]

posted_links = set()
last_topics = []

async def rewrite_news_ai(title, desc):
    """ИИ превращает новость в мировой виральный пост"""
    prompt = (
        f"Напиши вирусный аналитический пост для крупного международного Телеграм-канала.\n"
        f"НОВОСТЬ: {title}. {desc}\n\n"
        f"ИНСТРУКЦИЯ:\n"
        f"1. СТИЛЬ: Глобальный, дерзкий, экспертный. Текст от 350 до 700 символов.\n"
        f"2. ПОЗИЦИЯ: Прогрессивная, проукраинская, осуждающая агрессию.\n"
        f"3. ОФОРМЛЕНИЕ: Мощный заголовок капсом, абзацы, уместные эмодзи.\n"
        f"4. ФИНАЛ: Добавь жесткую ПРОВОКАЦИЮ или острый вопрос ко ВСЕМ думающим людям.\n"
        f"Пиши на русском языке."
    )
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OR_KEY}",
                "HTTP-Referer": "https://streamlit.io"
            },
            json={
                "model": "openrouter/auto",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=45
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Ошибка OpenRouter: {e}")
        return None

async def post_engine():
    """Основной цикл бота"""
    logging.info("БОТ ЗАПУЩЕН И МОНИТОРИТ НОВОСТИ")
    while True:
        try:
            logging.info("--- Начинаю поиск свежего контента ---")
            time_threshold = datetime.now() - timedelta(hours=10)
            
            all_entries = []
            for url in RSS_SOURCES:
                feed = feedparser.parse(url)
                all_entries.extend(feed.entries)
            
            random.shuffle(all_entries)

            post_sent = False
            for entry in all_entries:
                try:
                    pub_date = datetime(*entry.published_parsed[:6])
                except: continue
                
                title_lower = entry.title.lower()
                is_trash = any(word in title_lower for word in EXCLUDE_WORDS)
                is_duplicate = any(word in title_lower for word in last_topics[-3:])
                
                if pub_date > time_threshold and entry.link not in posted_links and not is_trash and not is_duplicate:
                    logging.info(f"Выбрана новость: {entry.title}")
                    description = getattr(entry, 'description', '')
                    viral_text = await rewrite_news_ai(entry.title, description)
                    
                    if viral_text and len(viral_text) > 250:
                        final_post = f"{viral_text}\n\n<a href='{entry.link}'>🔗 Источник</a>"
                        
                        await bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=final_post,
                            parse_mode="HTML"
                        )
                        
                        posted_links.add(entry.link)
                        last_topics.append(entry.title.split()[0].lower())
                        
                        logging.info("Пост опубликован! Сон 15 минут.")
                        post_sent = True
                        await asyncio.sleep(900) 
                        break 
            
            if not post_sent:
                logging.info("Новых новостей нет, подожду 5 минут...")
                await asyncio.sleep(300)

        except Exception as e:
            logging.error(f"Критическая ошибка в цикле: {e}")
            await asyncio.sleep(60)

def run_async_bot():
    """Запуск асинхронного цикла в отдельном потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(post_engine())

# --- ИНТЕРФЕЙС STREAMLIT ---
st.set_page_config(page_title="Info Sphere AI v2.2", page_icon="🗞")
st.title("🗞 Редакция Info Sphere AI")

if "bot_thread_started" not in st.session_state:
    st.session_state.bot_thread_started = True
    # Запускаем фоновый поток
    thread = threading.Thread(target=run_async_bot, daemon=True)
    thread.start()
    st.success("🚀 Система мониторинга запущена в фоне!")
else:
    st.info("✅ Статус: Мониторинг мировых новостей активен.")

st.write("---")
st.write("**Последние действия:**")
st.caption("Бот работает автоматически раз в 15 минут. Логи можно посмотреть в консоли Streamlit.")
