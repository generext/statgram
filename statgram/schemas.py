from pydantic import BaseModel
from typing import Union, Optional, Dict

class InitBotSchema(BaseModel):
    """
    Схема для добавления Telegram-бота к пользователю.
    """
    api_key: str
    chatbot_username: str

class AddChatbotUsernameResponseData(BaseModel):
    exist: bool  # Indicates if the chatbot already exists in the system
    new: bool    # Indicates if the chatbot was newly added
    user_id: str

class ResponseAddChatbotUsernameSchema(BaseModel):
    message: str  # A message describing the result of the operation
    data: Optional[AddChatbotUsernameResponseData]  # The response data with details about the chatbot status

class ChatbotInfo(BaseModel):
    id: int  # Уникальный идентификатор бота
    is_bot: bool  # Всегда True, так как это бот
    first_name: str  # Имя бота
    username: Optional[str] = None  # Username бота (может отсутствовать)
    can_join_groups: Optional[bool] = None  # Может ли бот добавляться в группы
    can_read_all_group_messages: Optional[bool] = None  # Читает ли бот все сообщения в группах
    supports_inline_queries: Optional[bool] = None  # Поддерживает ли бот inline-режим

class MessageSchema(BaseModel):
    chat_id: Union[int, str, None] = None
    text: str = None
    parse_mode: Optional[str] = None
    message_thread_id: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True

class MessagesResponse(BaseModel):
    messages: Dict[str, MessageSchema]
