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
        self.view_url = f"https://gateway.statgram.org/v1/library/view-message/{{chat_id}}?api_token={token}"
        self.delete_url = f"https://gateway.statgram.org/v1/library/delete-message/{{chat_id}}?api_token={token}"
        self.is_postgres_added = False

        # Запускаем поток для периодического GET-запроса
        self._start_periodic_get_requests()
        self.init_ping()


    def init_ping(self):
        """
        Выполняет проверочный запрос к endpoint /v1/auth/check-init.
        """
        url = "https://gateway.statgram.org/v1/auth/check-init"
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            print("✅ Пинг успешен, соединение установлено.")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка пинга: {e}")
            return None

    def _start_periodic_get_requests(self):
        """
        Запускает поток, который выполняет GET-запросы раз в секунду и обрабатывает сообщение.
        """
        def periodic_get():
            while True:
                chat_id = "example_chat_id"  # Здесь должен быть актуальный chat_id для запроса
                try:
                    # Получаем сообщение
                    response = requests.get(self.view_url.format(chat_id=chat_id))
                    if response.status_code == 200:
                        data = response.json()
                        if data:  # Если сообщение не пустое
                            try:
                                # Преобразуем данные в объект MessageSchema и отправляем сообщение
                                message_data = MessageSchema(**data)
                                asyncio.run(self.send_message(message_data))

                                # Удаляем сообщение после успешной отправки
                                self.delete_message(chat_id)
                            except Exception as e:
                                print(f"Ошибка обработки сообщения: {e}")
                        else:
                            print("Нет новых сообщений.")
                    else:
                        print(f"GET {self.view_url} -> Status: {response.status_code}")
                except Exception as e:
                    print(f"Ошибка при выполнении GET-запроса: {e}")
                time.sleep(1)  # Пауза в 1 секунду

        # Запускаем поток
        thread = threading.Thread(target=periodic_get, daemon=True)
        thread.start()

    def init_ping(self):
        pass

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
            payload = {"postgres_url": postgres_url, "user_id": 1}  # Пример user_id, заменить на актуальный
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}"
            }

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                print(f"✅ Ответ от сервера: {data}")
                return data
            except requests.exceptions.RequestException as e:
                print(f"❌ Ошибка при запросе к API: {e}")
                return None
