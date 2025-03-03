import asyncio
import logging
import time
import urllib.parse
import requests
import aiohttp

from aiogram import Bot
from fastapi import HTTPException
from .schemas import MessageSchema, InitBotSchema, ResponseAddChatbotUsernameSchema, ChatbotInfo
from .core_requests import init_bot_connection

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Statgram:
    def __init__(self, token: str, bot: Bot):
        """
        Инициализация Statgram с токеном бота и настройкой API.

        :param token: Токен Telegram-бота.
        :param bot: Инстанс aiogram.Bot.
        """
        self.token = token
        self.bot = bot
        self.view_url = f"https://gateway.statgram.org/v1/library/view-message?api_token={token}"
        self.delete_url = f"https://gateway.statgram.org/v1/library/delete-message?api_token={token}&chat_id={{chat_id}}"
        self.is_postgres_added = False
        self.client_id = None

        self.bot_username = self.get_bot_username()
        self.init_ping()

    def init_ping(self):
        """
        Выполняет проверочный запрос к endpoint /v1/auth/check-init.
        """
        init_data = InitBotSchema(api_key=self.token, chatbot_username=self.bot_username)
        response_data = init_bot_connection(init_data)
        response = ResponseAddChatbotUsernameSchema(**response_data)
        if not response.message:
            logger.error("❌ Ошибка пинга: API key не существует")
            raise HTTPException(status_code=404, detail="API key does not exist")

        if response.data and response.data.exist:
            self.client_id = response.data.user_id
            logger.info("✅ Новый коннект установлен.")
        else:
            logger.info("✅ Пинг успешен, соединение установлено.")

    def get_bot_username(self) -> str:
        """
        Получает имя пользователя (username) бота.

        :return: Username бота или "unknown_bot" в случае ошибки.
        """
        try:
            bot_info: ChatbotInfo = asyncio.run(self.bot.get_me())
            return bot_info.username
        except Exception as e:
            logger.error("❌ Ошибка при получении username бота: %s", e)
            return "unknown_bot"

    def connect_postgresql(self, host: str, port: int, user: str, password: str, database: str):
        """
        Создаёт URL для PostgreSQL и отправляет POST-запрос к `/v1/auth/add-postgres`.

        :param host: Хост базы данных.
        :param port: Порт базы данных.
        :param user: Имя пользователя.
        :param password: Пароль.
        :param database: Имя базы данных.
        :return: Ответ API или None в случае ошибки.
        """
        if self.is_postgres_added:
            return
        self.is_postgres_added = True

        encoded_user = urllib.parse.quote(user)
        encoded_password = urllib.parse.quote(password)
        postgres_url = f"postgresql://{encoded_user}:{encoded_password}@{host}:{port}/{database}"
        url = "https://gateway.statgram.org/v1/auth/add-postgres"
        payload = {"postgres_url": postgres_url, "api_key": self.token}

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info("Ответ от сервера: %s", data)
            return data
        except requests.exceptions.RequestException as e:
            logger.error("❌ Ошибка при запросе к API: %s", e)
            return None

    async def _async_log(self, message_data: MessageSchema) -> dict:
        """
        Асинхронно отправляет лог.

        :param message_data: Данные сообщения для логирования.
        :return: Результат запроса.
        """
        url = "https://logbox.statgram.org/log"
        # Если есть атрибут data – используем его, иначе берем text
        data_content = getattr(message_data, "data", getattr(message_data, "text", None))
        payload = {"api_key": self.token, "topic": "log", "data": data_content}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    response.raise_for_status()
                    result = await response.json()
                    logger.info("Лог отправлен: %s", result)
                    return result
        except Exception as e:
            logger.error("Ошибка отправки лога: %s", e)
            return {}

    def log(self, message_data: MessageSchema) -> None:
        """
        Логирует сообщение, отправка происходит асинхронно.
        """
        asyncio.create_task(self._async_log(message_data))

    async def send_message(self, data: MessageSchema):
        """
        Асинхронно отправляет сообщение через Telegram-бота.

        :param data: Объект MessageSchema с параметрами сообщения.
        """
        try:
            await self.bot.send_message(**data.model_dump())
        except Exception as e:
            logger.error("Ошибка отправки сообщения: %s", e)

    def delete_message(self, chat_id: str):
        """
        Удаляет сообщение по chat_id.

        :param chat_id: Идентификатор чата.
        """
        try:
            url = self.delete_url.format(chat_id=chat_id)
            response = requests.delete(url)
            if response.status_code == 200:
                logger.info("Сообщение с chat_id=%s успешно удалено.", chat_id)
            else:
                logger.error("Ошибка удаления сообщения: Status %s", response.status_code)
        except requests.exceptions.RequestException as e:
            logger.error("Ошибка при запросе на удаление сообщения: %s", e)

    async def periodic_get(self):
        """
        Асинхронно выполняет GET-запросы раз в секунду и обрабатывает сообщения.
        """
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(self.view_url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data:
                                try:
                                    message_data = MessageSchema(**data)
                                    await self.send_message(message_data)
                                except Exception as e:
                                    logger.error("Ошибка обработки сообщения: %s", e)
                        else:
                            text = await response.text()
                            logger.error("GET %s -> Status: %s | %s", self.view_url, response.status, text)
                except Exception as e:
                    logger.error("Ошибка при выполнении GET-запроса: %s", e)
                await asyncio.sleep(1)

    def start_periodic_get(self):
        """
        Запускает асинхронную задачу для периодических GET-запросов.
        Данный метод должен быть вызван из асинхронного контекста.
        """
        asyncio.create_task(self.periodic_get())
