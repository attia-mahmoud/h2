from enum import Enum, auto

class ClientState(Enum):
    IDLE = auto()
    WAITING_PREFACE = auto()
    WAITING_ACK = auto()
    SENDING_FRAMES = auto()
    RECEIVING_FRAMES = auto()
    CLOSING = auto()
    CLOSED = auto()

class ServerState(Enum):
    IDLE = auto()
    WAITING_PREFACE = auto()
    PREFACE_RECEIVED = auto()
    SETTINGS_ACKED = auto()
    WAITING_ACK = auto()
    RECEIVING_TEST_FRAMES = auto()
    RECEIVING_CLOSING_FRAMES = auto()
    SENDING_FRAMES = auto()
    CLOSING = auto()
    CLOSED = auto()