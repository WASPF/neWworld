import asyncio
import requests
import streamlit as st
import logging
import feedparser
import time
from datetime import datetime, timedelta
from aiogram import Bot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- КОНФИГУРАЦИЯ ---
TOKEN = st.secrets.get("NEWS_BOT_TOKEN")
OR_KEY = st.secrets.get("OPENROUTER_API_KEY")
CHANNEL_ID = "@info_sphere_tg" 

bot = Bot(token=TOKEN)

# Источники (расширил список для разнообразия тем)
RSS_SOURCES = [
    "https://news.google.com/rss/search?q=Ukraine+tech+war+world&hl=uk&gl=UA&ceid=UA:uk",
    "https://www.unian.net/rss",
    "https://censor.net/includes/news_ru.xml",
    "https://nv.ua/rss/all.xml",
    "https://uapress.info/rss/all.xml"
]

posted_links = set()
last_topics = [] # Храним последние темы, чтобы не повторяться

async def rewrite_news_ai(title, desc):
    """ИИ с четкой УКРАИНСКОЙ позицией и провокацией в конце"""
    
    prompt = (
        f"Напиши вирусный пост для украинского Телеграм-канала. "
        f"НОВОСТЬ: {title}. {desc}\n\n"
        f"ИНСТРУКЦИЯ:\n"
        f"1. Позиция: СТРОГО ПРОУКРАИНСКАЯ. Акцент на защите наших интересов, силе Украины и важности событий для нашей победы и будущего.\n"
        f"2. Стиль: Живой, дерзкий, патриотичный, но не 'дешевый кликбейт'. Текст от 350 символов.\n"
        f"3. Обязательно используй абзацы и эмодзи.\n"
        f"4. ФИНАЛ: Добавь жесткий провокационный вопрос к читателям, который заставит их спорить и обсуждать тему в комментариях.\n"
        f"Текст пиши на русском языке (или украинском, если канал на нем)."
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
        
        # Берем все новости из всех лент в один список
        all_entries = []
        for url in RSS_SOURCES:
            feed = feedparser.parse(url)
            all_entries.extend(feed.entries)
        
        # Перемешиваем, чтобы не шли новости только из одного источника
        random.shuffle(all_entries)

        for entry in all_entries:
            try:
                pub_date = datetime(*entry.published_parsed[:6])
            except: continue
            
            # Проверяем: свежая ли, не постили ли уже и нет ли 'Венгрии' слишком часто
            is_duplicate_topic = any(word in entry.title.lower() for word in last_topics[-3:])
            
            if pub_date > time_limit and entry.link not in posted_links and not is_duplicate_topic:
                
                logging.info(f"Обработка: {entry.title}")
                description = getattr(entry, 'description', '')
                viral_text = await rewrite_news_ai(entry.title, description)
                
                if viral_text and len(viral_text) > 250:
                    try:
                        final_post = f"{viral_text}\n\n<a href='{entry.link}'>🔗 Источник</a>"
                        await bot.send_message(CHANNEL_ID, final_text, parse_mode="HTML")
                        
                        posted_links.add(entry.link)
                        # Запоминаем ключевое слово из заголовка, чтобы не частить с темой
                        last_topics.append(entry.title.split()[0].lower()) 
                        
                        logging.info("--- ПОСТ ОПУБЛИКОВАН. Ухожу в сон на 15 минут ---")
                        # СТРОГАЯ ПАУЗА 15 МИНУТ после поста
                        await asyncio.sleep(900) 
                        break # Выходим из поиска, цикл while начнется заново через 15 мин
                    except Exception as e:
                        logging.error(f"Ошибка ТГ: {e}")
        
        # Если ничего нового не нашли, ждем 2 минуты и проверяем снова
        await asyncio.sleep(120)

if __name__ == "__main__":
    st.set_page_config(page_title="Info Sphere AI")
    st.title("🗞 Info Sphere: Редакция v2.0")
    st.write("Настройка: Проукраинская позиция, интервал 15 минут.")
    
    if "aggregator_v2" not in st.session_state:
        st.session_state.aggregator_v2 = True
        import random # Добавил тут, чтобы перемешивание работало
        asyncio.run(post_engine())
