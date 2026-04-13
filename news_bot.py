import asyncio
import requests
import streamlit as st
import os
import logging
import feedparser
from datetime import datetime, timedelta
from aiogram import Bot

# Настройка логов
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- КОНФИГУРАЦИЯ ---
TOKEN = st.secrets.get("NEWS_BOT_TOKEN")
OR_KEY = st.secrets.get("OPENROUTER_API_KEY")
CHANNEL_ID = "@info_sphere_tg"  # Твой канал

bot = Bot(token=TOKEN)

# Список источников (Мировые новости, технологии, наука)
RSS_SOURCES = [
    "https://news.google.com/rss?hl=ru&gl=UA&ceid=UA:ru",
    "https://www.unian.net/rss",
    "https://lenta.ru/rss/news",
    "https://www.bbc.co.uk/news/world/rss.xml",
    "https://www.theguardian.com/world/rss",
    "https://naked-science.ru/feed" # Наука
]

# Хранилище опубликованных ссылок (в памяти)
posted_links = set()

async def rewrite_news_ai(title, desc):
    """ИИ делает пост вирусным и провокационным"""
    prompt = (
        f"Напиши вирусный пост для Telegram на основе этой новости. "
        f"Стиль: агрессивный, шокирующий, захватывающий. Минимум 300 символов. "
        f"Используй эмодзи. В самом конце обязательно добавь ОСТРУЮ ПРОВОКАЦИЮ или "
        f"дерзкий вопрос, чтобы заставить людей спорить в комментариях. "
        f"Новость: {title}. {desc}"
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
            timeout=30
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Ошибка ИИ: {e}")
        return None

async def post_engine():
    """Главный двигатель: парсинг и посты каждые 15 минут"""
    while True:
        logging.info("Сканирую новости...")
        # Новости не старше 10 часов
        time_threshold = datetime.now() - timedelta(hours=10)
        
        found_something = False
        
        for url in RSS_SOURCES:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                try:
                    pub_date = datetime(*entry.published_parsed[:6])
                except: continue
                
                if pub_date > time_threshold and entry.link not in posted_links:
                    logging.info(f"Новая новость: {entry.title}")
                    
                    # Рерайт через ИИ
                    description = getattr(entry, 'description', '')
                    viral_text = await rewrite_news_ai(entry.title, description)
                    
                    if viral_text and len(viral_text) > 200:
                        try:
                            # Добавляем ссылку на источник в кнопку или текст
                            final_text = f"{viral_text}\n\n<a href='{entry.link}'>🔗 Источник</a>"
                            
                            await bot.send_message(
                                chat_id=CHANNEL_ID,
                                text=final_text,
                                parse_mode="HTML"
                            )
                            posted_links.add(entry.link)
                            logging.info("Пост улетел в канал!")
                            
                            # Ждем 15 минут до следующей новости
                            await asyncio.sleep(900) 
                            found_something = True
                            break # Выходим из цикла источников
                        except Exception as e:
                            logging.error(f"Ошибка ТГ: {e}")
            
            if found_something: break
            
        logging.info("Цикл завершен, жду 5 минут до новой проверки...")
        await asyncio.sleep(300)

if __name__ == "__main__":
    st.title("🗞 Info Sphere AI Aggregator")
    st.info("Бот активно ищет новости и делает их вирусными. Ожидайте посты в канале.")
    
    if "aggregator_run" not in st.session_state:
        st.session_state.aggregator_run = True
        asyncio.run(post_engine())