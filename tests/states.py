from enum import Enum, auto

class ClientState(Enum):
    IDLE = auto()
    PREFACE_SENT = auto()
    SETTINGS_ACKED = auto()
    SENDING_FRAMES = auto()
    WAITING_RESPONSE = auto()
    CLOSING = auto()
    CLOSED = auto()

class ServerState(Enum):
    IDLE = auto()
    WAITING_PREFACE = auto()
    PREFACE_RECEIVED = auto()
    SETTINGS_ACKED = auto()
    PROCESSING_FRAMES = auto()
    CLOSING = auto()
    CLOSED = auto()