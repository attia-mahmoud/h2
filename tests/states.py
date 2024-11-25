from enum import Enum, auto

class ClientState(Enum):
    IDLE = auto()
    PREFACE_SENT = auto()
    SETTINGS_ACKED = auto()
    SENDING_FRAMES = auto()
    RECEIVING_FRAMES = auto()
    CLOSING = auto()
    CLOSED = auto()

class ServerState(Enum):
    IDLE = auto()
    WAITING_PREFACE = auto()
    PREFACE_RECEIVED = auto()
    SETTINGS_ACKED = auto()
    RECEIVING_FRAMES = auto()
    SENDING_FRAMES = auto()
    CLOSING = auto()
    CLOSED = auto()