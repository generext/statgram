from pydantic import BaseModel
from typing import Union, List, Optional
from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ForceReply,
    MessageEntity
)

class MessageSchema(BaseModel):
    chat_id: Union[int, str]
    text: str
    parse_mode: Optional[str] = None
    entities: Optional[List[MessageEntity]] = None
    disable_web_page_preview: Optional[bool] = None
    message_thread_id: Optional[int] = None
    disable_notification: Optional[bool] = None
    protect_content: Optional[bool] = None
    reply_to_message_id: Optional[int] = None
    allow_sending_without_reply: Optional[bool] = None
    reply_markup: Optional[
        Union[InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply]
    ] = None


class InitBotSchema(BaseModel):
    """
    Схема для добавления Telegram-бота к пользователю.
    """
    api_key: str
    chatbot_username: str


class AddChatbotUsernameResponseData(BaseModel):
    exist: bool  # Indicates if the chatbot already exists in the system
    new: bool    # Indicates if the chatbot was newly added
    user_id: int

class ResponseAddChatbotUsernameSchema(BaseModel):
    message: str  # A message describing the result of the operation
    data: AddChatbotUsernameResponseData  # The response data with details about the chatbot status