
import httpx
import requests
from .schemas import InitBotSchema

# Define the base URL
GATEWAY_BASE_URL = "https://gateway.statgram.org"
LOGBOX_BASE_URL = "https://logbox.statgram.org"

CHECK_INIT = "/v1/auth/check-init"
ADD_USERNAME = "/v1/auth/add-chatbot-username"


def init_bot_connection(data: InitBotSchema):
    response = requests.post(f"{GATEWAY_BASE_URL}{ADD_USERNAME}", json=data.dict())
    response.raise_for_status()
    return response.json()
