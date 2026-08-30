import sys
import types

# ragas 0.4.3 imports a module langchain-community 0.4.2 removed.
# We register a stub so the import succeeds; we use Gemini, never Vertex AI.
MODULE = "langchain_community.chat_models.vertexai"

def install_stub():
    try:
        __import__(MODULE)
        return False
    except ImportError:
        pass

    class ChatVertexAI:
        pass

    stub = types.ModuleType(MODULE)
    stub.ChatVertexAI = ChatVertexAI
    sys.modules[MODULE] = stub
    return True

install_stub()
