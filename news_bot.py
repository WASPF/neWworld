import asyncio
import requests
import streamlit as st
import logging
import feedparser
import random
from datetime import datetime, timedelta
from aiogram import Bot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- КОНФИГУРАЦИЯ ---
TOKEN = st.secrets.get("NEWS_BOT_TOKEN")
OR_KEY = st.secrets.get("OPENROUTER_API_KEY")
CHANNEL_ID = "@info_sphere_tg" 

bot = Bot(token=TOKEN)

RSS_SOURCES = [
    "https://news.google.com/rss/search?q=Ukraine+war+politics+economy&hl=uk&gl=UA&ceid=UA:uk",
    "https://www.unian.net/rss",
    "https://censor.net/includes/news_ru.xml",
    "https://nv.ua/rss/all.xml"
]

# Исключаем темы, которые не подходят для серьезного канала
EXCLUDE_WORDS = ['гороскоп', 'диета', 'георгин', 'кожа', 'цветы', 'шоу-биз', 'бритни спирс']

posted_links = set()
last_topics = []

async def rewrite_news_ai(title, desc):
    """ИИ с проукраинской позицией"""
    prompt = (
        f"Напиши вирусный пост для украинского канала.\n"
        f"НОВОСТЬ: {title}. {desc}\n\n"
        f"ИНСТРУКЦИЯ:\n"
        f"1. Позиция: Четко проукраинская. Акцент на важных событиях, победах и вызовах для страны.\n"
        f"2. Текст: Длинный (от 350 симв.), дерзкий, аналитический, с эмодзи.\n"
        f"3. ФИНАЛ: Жесткая провокация для дискуссии в комментариях.\n"
        f"Пиши на русском языке (так как источники смешанные)."
    )
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "https://streamlit.io"},
            json={"model": "openrouter/auto", "messages": [{"role": "user", "content": prompt}]},
            timeout=40
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Ошибка ИИ: {e}")
        return None

async def post_engine():
    while True:
        logging.info("Начинаю круг проверки источников...")
        time_limit = datetime.now() - timedelta(hours=8)
        
        all_entries = []
        for url in RSS_SOURCES:
            feed = feedparser.parse(url)
            all_entries.extend(feed.entries)
        
        random.shuffle(all_entries)

        for entry in all_entries:
            try:
                pub_date = datetime(*entry.published_parsed[:6])
            except: continue
            
            # Фильтруем мусор и дубли тем
            title_lower = entry.title.lower()
            is_trash = any(word in title_lower for word in EXCLUDE_WORDS)
            is_duplicate = any(word in title_lower for word in last_topics[-3:])
            
            if pub_date > time_limit and entry.link not in posted_links and not is_trash and not is_duplicate:
                
                logging.info(f"Обработка: {entry.title}")
                description = getattr(entry, 'description', '')
                viral_text = await rewrite_news_ai(entry.title, description)
                
                if viral_text and len(viral_text) > 200:
                    try:
                        # ТУТ ИСПРАВЛЕНА ОШИБКА name 'final_text' is not defined
                        final_post = f"{viral_text}\n\n<a href='{entry.link}'>🔗 Источник</a>"
                        
                        await bot.send_message(CHANNEL_ID, final_post, parse_mode="HTML")
                        
                        posted_links.add(entry.link)
                        last_topics.append(entry.title.split()[0].lower()) 
                        
                        logging.info("--- ПОСТ ОПУБЛИКОВАН. Сон 15 мин ---")
                        await asyncio.sleep(900) 
                        break 
                    except Exception as e:
                        logging.error(f"Ошибка ТГ: {e}")
        
        await asyncio.sleep(180)

if __name__ == "__main__":
    st.title("🗞 Info Sphere: Редакция v2.1 (Fixed)")
    
    if "aggregator_run_v21" not in st.session_state:
        st.session_state.aggregator_run_v21 = True
        asyncio.run(post_engine())
