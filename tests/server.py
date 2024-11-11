import h2.connection
import h2.config
import h2.events
import socket
import select
import yaml
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

@dataclass
class ServerResponse:
    def __init__(self, headers: List[Tuple[str, str]], body: str):
        self.headers = headers
        self.body = body


class TestCaseManager:
    def __init__(self, yaml_path: str):
        self.yaml_path = yaml_path
        self.test_data = self._load_yaml()
        self.logger = logging.getLogger(__name__)

    def _load_yaml(self) -> Dict:
        """Load and parse YAML test configuration"""
        try:
            with open(self.yaml_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"{self.yaml_path} not found")
        except yaml.YAMLError:
            raise ValueError(f"Invalid YAML in {self.yaml_path}")

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
            self._process_requests()
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
                self.conn.update_settings(frame.get('settings', {}))
            
            self.client_socket.sendall(self.conn.data_to_send())

    def _format_headers(self, headers: Dict) -> List[Tuple[str, str]]:
        """Format headers from frame configuration"""
        formatted_headers = []
        
        if 'pseudo_headers' in headers:
            for name, value in headers['pseudo_headers'].items():
                formatted_headers.append((f":{name}", str(value)))
        
        if 'regular_headers' in headers:
            for name, value in headers['regular_headers'].items():
                formatted_headers.append((name, str(value)))
        
        return formatted_headers

    def _process_requests(self) -> None:
        """Process incoming requests"""
        self.logger.info("Waiting for request...")
        while True:
            data = self.client_socket.recv(65535)
            if not data:
                self.logger.info("Connection closed by client")
                break
            
            events = self.conn.receive_data(data)
            self.logger.info(f"Received events: {events}")
            
            for event in events:
                if isinstance(event, h2.events.RequestReceived):
                    self.logger.info("Request received, sending response...")
                    self._handle_request(event)
                elif isinstance(event, h2.events.DataReceived):
                    self.logger.info(f"Received DATA frame with payload size: {len(event.data)} bytes")
            
            outbound_data = self.conn.data_to_send()
            if outbound_data:
                self.client_socket.sendall(outbound_data)

    def _handle_request(self, event: h2.events.RequestReceived) -> None:
        """Handle incoming request"""
        self.logger.info(f"Request headers: {event.headers}")
        
        # Send response
        for frame in self.test_case['server_frames']:
            frame_type = FrameType(frame['type'].upper())
            if frame_type == FrameType.HEADERS:
                stream_id = frame.get('stream_id', 1)
                end_stream = 'END_STREAM' in frame.get('flags', [])
                headers = self._format_headers(frame.get('headers', {}))
                body = frame.get('body', '')

                response = ServerResponse(headers=headers, body=body)
            
                # Send response headers
                self.conn.send_headers(
                    stream_id=stream_id,
                    headers=response.headers,
                    end_stream=False
                )
                
                # Send response data
                self.conn.send_data(
                    stream_id=stream_id,
                    data=response.body.encode('utf-8'),
                    end_stream=True
                )
                
                self.client_socket.sendall(self.conn.data_to_send())

                self.logger.info("Response sent")

            elif frame_type == FrameType.RST_STREAM:
                stream_id = frame.get('stream_id')
                error_code = frame.get('error_code', 'CANCEL')
                self.conn.reset_stream(stream_id, error_code=getattr(h2.errors.ErrorCodes, error_code))
            

    def close(self) -> None:
        """Close the connection"""
        self.client_socket.close()
        self.logger.info("Connection closed")

class HTTP2Server:
    def __init__(self, host: str = 'localhost', port: int = 7700, yaml_path: str = 'test_cases.yaml'):
        self.host = host
        self.port = port
        self.sock = None
        self.test_manager = TestCaseManager(yaml_path)
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