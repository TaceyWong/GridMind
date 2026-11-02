from gridmind.core.security import UserContext
from gridmind.services.chat import ChatService


def get_chat_service() -> ChatService:
    return ChatService()


def get_user_context() -> UserContext:
    return UserContext()
