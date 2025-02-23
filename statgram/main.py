from aiogram import Bot
import requests
import threading
import time
import asyncio
from .schemas import MessageSchema
import urllib.parse
from .core_requests import init_bot_connection
from .schemas import InitBotSchema, ResponseAddChatbotUsernameSchema, ChatbotInfo
from fastapi import HTTPException
import aiohttp


class Statgram:
    def __init__(self, token: str, bot: Bot):
        """
        Инициализация StatGram с токеном бота и настройкой GET-запросов.
        :param token: Токен Telegram-бота.
        :param bot: Инстанс aiogram.Bot.
        """
        self.token = token
        self.bot = bot
        self.view_url = f"https://gateway.statgram.org/v1/library/view-message?api_token={token}"
        self.is_postgres_added = False
        self.client_id = None

        # Запускаем поток для периодического GET-запроса
        self.bot_username = self.get_bot_username()
        self._start_periodic_get_requests()
        self.init_ping()


    def init_ping(self):
        """
        Выполняет проверочный запрос к endpoint /v1/auth/check-init.
        """
        response: ResponseAddChatbotUsernameSchema = ResponseAddChatbotUsernameSchema(**init_bot_connection(
            InitBotSchema(
                api_key=self.token, 
                chatbot_username=self.bot_username
            )
        ))
        print("✅ response", response)
        if response.data.exist:
            self.client_id = response.data.user_id
            if response.data.new:
                print("✅ Новый коннект установлен.")
            else:
                print("✅ Пинг успешен, соединение установлено.")
        else:
            print(f"❌ Ошибка пинга")
            raise HTTPException(status_code=404, detail="API key does not exist")

    def get_bot_username(self) -> str:
        """
        Получает имя пользователя (username) бота.
        """
        try:
            bot_info: ChatbotInfo = asyncio.run(self.bot.get_me())  # Запрос данных о боте
            return bot_info.username
        except Exception as e:
            print(f"❌ Ошибка при получении username бота: {e}")
            return "unknown_bot"  # Фолбэк, если произошла ошибка

    def connect_postgresql(self, host: str, port: int, user: str, password: str, database: str):
        """
        Создаёт URL для PostgreSQL и отправляет POST-запрос к `/v1/auth/add-postgres`.
        """
        if not self.is_postgres_added:
            self.is_postgres_added = True
            encoded_user = urllib.parse.quote(user)
            encoded_password = urllib.parse.quote(password)

            postgres_url = f"postgresql://{encoded_user}:{encoded_password}@{host}:{port}/{database}"
            url = "https://gateway.statgram.org/v1/auth/add-postgres"
            payload = {"postgres_url": postgres_url, "api_key": self.token}  # Пример user_id, заменить на актуальный

            try:
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()
                data = response.json()
                print(f"✅ Ответ от сервера: {data}")
                return data
            except requests.exceptions.RequestException as e:
                print(f"❌ Ошибка при запросе к API: {e}")
                return None

    async def _async_log(self, message_data: MessageSchema) -> dict:
        """
        Асинхронная функция для отправки лога.
        """
        url = "https://logbox.statgram.org/log"
        try:
            # Пытаемся получить data, если её нет – берем text
            data = message_data.data
        except AttributeError:
            data = message_data.text

        payload = {
            "api_key": self.token,
            "topic": "log",
            "data": data
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    response.raise_for_status()  # Если статус не 200, будет выброшено исключение
                    result = await response.json()
                    print(f"✅ Лог отправлен: {result}")
                    return result
        except Exception as e:
            print(f"❌ Ошибка отправки лога: {e}")
            return {}

    def log(self, message_data: MessageSchema) -> None:
        """
        Публичный метод логирования. Он сразу возвращает управление,
        а отправка лога происходит в фоне.
        """
        # Запускаем асинхронную функцию как задачу (fire-and-forget)
        asyncio.create_task(self._async_log(message_data))
        # Возвращаем сразу, не дожидаясь завершения отправки лога

    async def send_message(self, data: MessageSchema):
        """
        Отправляет сообщение с помощью Telegram-бота.
        :param data: Объект MessageSchema с параметрами сообщения.
        """
        try:
            await self.bot.send_message(**data.model_dump())
        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}")

    def delete_message(self, chat_id: str):
        """
        Удаляет сообщение из очереди по chat_id.
        :param chat_id: Идентификатор чата для удаления сообщения.
        """
        try:
            response = requests.delete(self.delete_url.format(chat_id=chat_id))
            if response.status_code == 200:
                print(f"✅ Сообщение с chat_id={chat_id} успешно удалено.")
            else:
                print(f"❌ Ошибка удаления сообщения: Status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка при запросе на удаление сообщения: {e}")

    def _start_periodic_get_requests(self):
        """
        Запускает поток, который выполняет GET-запросы раз в секунду и обрабатывает сообщение.
        """
        def periodic_get():
            while True:
                try:
                    # Получаем сообщение
                    response = requests.get(self.view_url)
                    if response.status_code == 200:
                        data = response.json()
                        if data:  # Если сообщение не пустое
                            try:
                                # Преобразуем данные в объект MessageSchema и отправляем сообщение
                                message_data = MessageSchema(**data)
                                asyncio.run(self.send_message(message_data))

                                # Удаляем сообщение после успешной отправки
                            except Exception as e:
                                print(f"Ошибка обработки сообщения: {e}")
                        else:
                            print("Нет новых сообщений.")
                    else:
                        print(f"GET {self.view_url} -> Status: {response.status_code} | {response.text}")
                except Exception as e:
                    print(f"Ошибка при выполнении GET-запроса: {e}")
                time.sleep(1)  # Пауза в 1 секунду

        # Запускаем поток
        thread = threading.Thread(target=periodic_get, daemon=True)
        thread.start()
