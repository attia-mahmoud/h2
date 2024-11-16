import h2.connection
import h2.config
import h2.events
import socket
import select
import json
import ssl
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Dict, Optional, Any
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)

class FrameType(Enum):
    HEADERS = "HEADERS"
    SETTINGS = "SETTINGS"
    DATA = "DATA"
    WINDOW_UPDATE = "WINDOW_UPDATE"
    RST_STREAM = "RST_STREAM"
    PUSH_PROMISE = "PUSH_PROMISE"
    PING = "PING"
    GOAWAY = "GOAWAY"

@dataclass
class ServerResponse:
    def __init__(self, headers: List[Tuple[str, str]], body: str):
        self.headers = headers
        self.body = body


class TestCaseManager:
    def __init__(self, json_path: str):
        self.json_path = json_path
        self.test_data = self._load_json()
        self.logger = logging.getLogger(__name__)

    def _load_json(self) -> Dict:
        """Load and parse JSON test configuration"""
        try:
            with open(self.json_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"{self.json_path} not found")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in {self.json_path}")

    def find_test_case(self, test_id: int) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Find test case and its parent suite by ID"""
        for suite in self.test_data['test_suites']:
            for case in suite['cases']:
                if case['id'] == test_id:
                    return case, suite
        return None, None

class HTTP2Connection:
    def __init__(self, client_socket: socket.socket, addr: Tuple[str, int], test_case: Dict[str, Any]):
        self.client_socket = client_socket
        self.addr = addr
        self.test_case = test_case
        self.conn = None
        self.logger = logging.getLogger(__name__)

    def handle(self) -> None:
        """Handle client connection"""
        self.logger.info(f"Connection from {self.addr}")
        
        try:
            self._initialize_connection()
            self._handle_client_preface()
            self._send_server_frames()
        except Exception as e:
            self.logger.error(f"Error handling client: {e}", exc_info=True)
        finally:
            self.close()

    def _initialize_connection(self) -> None:
        """Initialize H2 connection"""
        config = h2.config.H2Configuration(client_side=False)
        self.conn = h2.connection.H2Connection(config=config)

    def _handle_client_preface(self) -> None:
        """Handle client preface"""
        self.logger.info("Waiting for client preface...")
        preface = self.client_socket.recv(24)
        if preface != b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n':
            raise ValueError(f"Invalid client preface: {preface}")
        self.logger.info("Valid client preface received")

    def _send_server_frames(self) -> None:
        """Send frames specified in test case"""
        for frame in self.test_case['server_frames']:
            frame_type = FrameType(frame['type'].upper())
            
            if frame_type == FrameType.SETTINGS:
                self._send_settings_frame(frame)
            elif frame_type == FrameType.HEADERS:
                self._send_headers_frame(frame)
            elif frame_type == FrameType.DATA:
                self._send_data_frame(frame)
            elif frame_type == FrameType.PUSH_PROMISE:
                self._send_push_promise_frame(frame)
            elif frame_type == FrameType.RST_STREAM:
                self._send_rst_stream_frame(frame)
            elif frame_type == FrameType.GOAWAY:
                self._send_goaway_frame(frame)
            elif frame_type == FrameType.PING:
                self._send_ping_frame(frame)

    def _send_settings_frame(self, frame: Dict) -> None:
        """Send a SETTINGS frame"""
        if frame.get('raw_payload', False) or 'stream_id' in frame:
            settings_payload = b''
            for setting, value in frame.get('settings', {}).items():
                setting_id = getattr(h2.settings.SettingCodes, setting)
                settings_payload += setting_id.to_bytes(2, byteorder='big')
                settings_payload += value.to_bytes(4, byteorder='big')
            
            frame_header = (
                len(settings_payload).to_bytes(3, byteorder='big') +  # Length
                b'\x04' +  # Type (4 for SETTINGS)
                (b'\x01' if 'ACK' in frame.get('flags', []) else b'\x00') +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')
            )
            
            self.client_socket.sendall(frame_header + settings_payload)
        else:
            self.conn.update_settings(frame.get('settings', {}))
            if 'ACK' in frame.get('flags', []):
                self.conn.acknowledge_settings()
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_headers_frame(self, frame: Dict) -> None:
        """Send a HEADERS frame"""
        if frame.get('raw_payload', False):
            headers = self._format_headers(frame.get('headers', {}))
            header_block = self.conn.encoder.encode(headers)
            
            frame_header = (
                len(header_block).to_bytes(3, byteorder='big') +  # Length
                b'\x01' +  # Type (1 for HEADERS)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 1).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + header_block)
        else:
            stream_id = frame.get('stream_id', 1)
            headers = self._format_headers(frame.get('headers', {}))
            end_stream = 'END_STREAM' in frame.get('flags', [])
            
            self.conn.send_headers(
                stream_id=stream_id,
                headers=headers,
                end_stream=end_stream
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_data_frame(self, frame: Dict) -> None:
        """Send a DATA frame"""
        if frame.get('raw_payload', False):
            data = frame.get('data', '').encode('utf-8')
            
            frame_header = (
                len(data).to_bytes(3, byteorder='big') +  # Length
                b'\x00' +  # Type (0 for DATA)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 1).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + data)
        else:
            stream_id = frame.get('stream_id', 1)
            data = frame.get('data', '').encode('utf-8')
            end_stream = 'END_STREAM' in frame.get('flags', [])
            
            self.conn.send_data(
                stream_id=stream_id,
                data=data,
                end_stream=end_stream
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_push_promise_frame(self, frame: Dict) -> None:
        """Send a PUSH_PROMISE frame"""
        if frame.get('raw_payload', False) or frame.get('stream_id', 0) == 0:
            headers = self._format_headers(frame.get('headers', {}))
            header_block = self.conn.encoder.encode(headers)
            
            # Create the frame payload
            frame_payload = frame.get('promised_stream_id', 2).to_bytes(4, byteorder='big')
            
            # Add padding length byte if PADDED flag is set
            if 'PADDED' in frame.get('flags', []):
                padding_length = frame.get('padding_length', 0)
                frame_payload = bytes([padding_length]) + frame_payload
            
            # Add header block
            frame_payload += header_block
            
            # Add padding if PADDED flag is set
            if 'PADDED' in frame.get('flags', []):
                frame_payload += b'\x00' * frame.get('padding_length', 0)
            
            frame_header = (
                len(frame_payload).to_bytes(3, byteorder='big') +  # Length
                b'\x05' +  # Type (5 for PUSH_PROMISE)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + frame_payload)
        else:
            stream_id = frame.get('stream_id', 1)
            promised_stream_id = frame.get('promised_stream_id', 2)
            headers = self._format_headers(frame.get('headers', {}))
            
            self.conn.push_stream(
                stream_id=stream_id,
                promised_stream_id=promised_stream_id,
                request_headers=headers
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_rst_stream_frame(self, frame: Dict) -> None:
        """Send a RST_STREAM frame"""
        if frame.get('raw_payload', False):
            error_code = getattr(h2.errors.ErrorCodes, frame.get('error_code', 'PROTOCOL_ERROR'))
            payload = error_code.to_bytes(4, byteorder='big')
            
            frame_header = (
                len(payload).to_bytes(3, byteorder='big') +  # Length
                b'\x03' +  # Type (3 for RST_STREAM)
                b'\x00' +  # Flags (no flags for RST_STREAM)
                frame.get('stream_id', 1).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + payload)
        else:
            stream_id = frame.get('stream_id', 1)
            error_code = frame.get('error_code', 'PROTOCOL_ERROR')
            
            self.conn.reset_stream(
                stream_id=stream_id,
                error_code=getattr(h2.errors.ErrorCodes, error_code)
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_goaway_frame(self, frame: Dict) -> None:
        """Send a GOAWAY frame"""
        if frame.get('raw_payload', False) or 'stream_id' in frame:
            # Convert error code to int if string provided
            if isinstance(frame.get('error_code'), str):
                error_code = getattr(h2.errors.ErrorCodes, frame['error_code'])
            else:
                error_code = frame.get('error_code', h2.errors.ErrorCodes.NO_ERROR)
            
            # Create payload: last_stream_id (4 bytes) + error_code (4 bytes)
            payload = (
                frame.get('last_stream_id', 0).to_bytes(4, byteorder='big') +
                error_code.to_bytes(4, byteorder='big')
            )
            
            # Add debug data if provided
            if 'debug_data' in frame:
                if isinstance(frame['debug_data'], str):
                    payload += frame['debug_data'].encode('utf-8')
                else:
                    payload += frame['debug_data']
            
            frame_header = (
                len(payload).to_bytes(3, byteorder='big') +  # Length
                b'\x07' +  # Type (7 for GOAWAY)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')  # Stream ID (normally 0)
            )
            
            self.client_socket.sendall(frame_header + payload)
        else:
            # Use h2 library's GOAWAY support
            error_code = frame.get('error_code', 'NO_ERROR')
            if isinstance(error_code, str):
                error_code = getattr(h2.errors.ErrorCodes, error_code)
                
            last_stream_id = frame.get('last_stream_id', 0)
            debug_data = frame.get('debug_data', b'').encode('utf-8') if isinstance(frame.get('debug_data'), str) else frame.get('debug_data', b'')
            
            self.conn.close_connection(
                error_code=error_code,
                last_stream_id=last_stream_id,
                additional_data=debug_data
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_ping_frame(self, frame: Dict) -> None:
        """Send a PING frame"""
        if frame.get('raw_payload', False) or 'stream_id' in frame:
            # Convert string payload to bytes if needed
            if isinstance(frame.get('payload'), str):
                payload = frame['payload'].encode('utf-8')
            else:
                payload = frame.get('payload', b'\x00' * 8)
            
            # Handle custom length if specified, otherwise ensure 8 bytes
            if 'force_length' in frame:
                if len(payload) > frame['force_length']:
                    payload = payload[:frame['force_length']]
                elif len(payload) < frame['force_length']:
                    payload = payload.ljust(frame['force_length'], b'\x00')
            else:
                # Default behavior: ensure exactly 8 bytes
                if len(payload) < 8:
                    payload = payload.ljust(8, b'\x00')
                elif len(payload) > 8:
                    payload = payload[:8]
            
            frame_header = (
                len(payload).to_bytes(3, byteorder='big') +  # Length (from payload)
                b'\x06' +  # Type (6 for PING)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + payload)
        else:
            # Use h2 library's PING support
            opaque_data = frame.get('payload', b'\x00' * 8)
            if isinstance(opaque_data, str):
                opaque_data = opaque_data.encode('utf-8')
            
            self.conn.ping(opaque_data)
            self.client_socket.sendall(self.conn.data_to_send())

    def _encode_flags(self, flags: List[str]) -> bytes:
        """Helper method to encode frame flags"""
        flag_byte = 0
        flag_mapping = {
            'END_STREAM': 0x1,
            'END_HEADERS': 0x4,
            'PADDED': 0x8,
            'PRIORITY': 0x20,
            'ACK': 0x1
        }
        for flag in flags:
            if flag in flag_mapping:
                flag_byte |= flag_mapping[flag]
        return bytes([flag_byte])

    def close(self) -> None:
        """Close the connection"""
        self.client_socket.close()
        self.logger.info("Connection closed")

class HTTP2Server:
    def __init__(self, host: str = 'localhost', port: int = 7700, json_path: str = 'test_cases.json'):
        self.host = host
        self.port = port
        self.sock = None
        self.test_manager = TestCaseManager(json_path)
        self.logger = logging.getLogger(__name__)

    def _setup_socket(self, test_id: int) -> None:
        """Setup server socket with test case configuration"""
        test_case, suite = self.test_manager.find_test_case(test_id)
        if not test_case:
            raise ValueError(f"Test {test_id} not found")

        self.logger.info(f"\nRunning test suite: {suite['name']}")
        self.logger.info(f"Section: {suite['section']}")
        self.logger.info(f"Description: {test_case['description']}")

        self._create_socket()
        self._configure_tls(test_case)
        self._bind_and_listen()

    def _create_socket(self) -> None:
        """Create and configure base socket"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def _configure_tls(self, test_case: Dict[str, Any]) -> None:
        """Configure TLS if specified in test case"""
        connection_settings = test_case.get('connection_settings', {})
        if connection_settings.get('tls_enabled', False):
            self.logger.info("Setting up TLS...")
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(certfile="certs/server.crt", keyfile="certs/server.key")
            self.sock = context.wrap_socket(self.sock, server_side=True)
            self.logger.info("TLS established")

    def _bind_and_listen(self) -> None:
        """Bind socket and start listening"""
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.sock.settimeout(10)

    def run(self, test_id: int) -> None:
        """Run the server for a specific test case"""
        test_case, suite = self.test_manager.find_test_case(test_id)
        if not test_case:
            raise ValueError(f"Test {test_id} not found")

        self._setup_socket(test_id)
        self.logger.info(f"Server listening on {self.host}:{self.port}")
        
        try:
            while True:
                client_socket, addr = self.sock.accept()
                connection = HTTP2Connection(client_socket, addr, test_case)
                connection.handle()
                break
        except KeyboardInterrupt:
            self.logger.info("\nShutting down server...")
        finally:
            if self.sock:
                self.sock.close()

def main():
    try:
        test_id = 8
        server = HTTP2Server()
        server.run(test_id)
    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()