from gridmind.services.chat import ChatService


def get_chat_service() -> ChatService:
    """Dependency provider for ChatService."""
    return ChatService()
