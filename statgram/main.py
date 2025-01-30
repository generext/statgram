from aiogram import Bot
import requests
import threading
import time
import asyncio
from .schemas import MessageSchema
import urllib.parse


class Statgram:
    def __init__(self, token: str, bot: Bot):
        """
        Инициализация StatGram с токеном бота и настройкой GET-запросов.
        :param token: Токен Telegram-бота.
        :param bot: Инстанс aiogram.Bot.
        """
        self.token = token
        self.bot = bot
        self.url = f"https://gateway.statgram.org/chatbot/messages?token={token}"
        self.is_postgres_added = False

        # Запускаем поток для периодического GET-запроса
        self._start_periodic_get_requests()

    def _start_periodic_get_requests(self):
        """
        Запускает поток, который выполняет GET-запросы раз в секунду и обрабатывает список MessageSchema.
        """
        def periodic_get():
            while True:
                try:
                    response = requests.get(self.url)
                    if response.status_code == 200:
                        data = response.json()  # Получаем данные в формате JSON
                        if isinstance(data, list):  # Убеждаемся, что это список
                            for item in data:
                                try:
                                    # Преобразуем каждый элемент в объект MessageSchema
                                    message_data = MessageSchema(**item)
                                    # Отправляем сообщение
                                    asyncio.run(self.send_message(message_data))
                                except Exception as e:
                                    print(f"Ошибка обработки элемента MessageSchema: {e}")
                        else:
                            print(f"Ответ не является списком: {data}")
                    else:
                        print(f"GET {self.url} -> Status: {response.status_code}")
                except Exception as e:
                    print(f"Ошибка при выполнении GET-запроса: {e}")
                time.sleep(1)  # Пауза в 1 секунду

        # Запускаем поток
        thread = threading.Thread(target=periodic_get, daemon=True)
        thread.start()

    async def send_message(self, data: MessageSchema):
        """
        Отправляет сообщение с помощью Telegram-бота.
        :param data: Объект MessageSchema с параметрами сообщения.
        """
        try:
            await self.bot.send_message(**data.model_dump())
        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}")


    def connect_postgresql(self, host: str, port: int, user: str, password: str, database: str):
        """
        Создаёт URL для PostgreSQL и отправляет POST-запрос к `https://gateway.statgram.org/chatbot/connect_postgresql`.
        """
        if not self.is_postgres_added:
            self.is_postgres_added = True
            # Кодируем user и password, чтобы избежать проблем с спецсимволами
            encoded_user = urllib.parse.quote(user)
            encoded_password = urllib.parse.quote(password)

            # Формируем PostgreSQL URL
            postgres_url = f"postgresql://{encoded_user}:{encoded_password}@{host}:{port}/{database}"

            url = "https://gateway.statgram.org/chatbot/connect_postgresql"
            payload = {"url": postgres_url}  # Передаём URL базы данных
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}"  # Передаём API-токен в заголовке
            }
            
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)  # Отправляем POST-запрос
                response.raise_for_status()  # Проверяем HTTP-ошибки (4xx, 5xx)
                data = response.json()  # Конвертируем ответ в JSON
                print(f"✅ Ответ от сервера: {data}")
                return data
            except requests.exceptions.RequestException as e:
                print(f"❌ Ошибка при запросе к API: {e}")
                return None
