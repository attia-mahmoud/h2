import h2.connection
import h2.events
import h2.config
import h2.settings
import socket
import yaml
import sys
import time
import logging
import ssl
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Dict, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)

class FrameType(Enum):
    HEADERS = "HEADERS"
    SETTINGS = "SETTINGS"
    DATA = "DATA"
    WINDOW_UPDATE = "WINDOW_UPDATE"
    RST_STREAM = "RST_STREAM"
    PRIORITY = "PRIORITY"

@dataclass
class TestResult:
    test_id: int
    success: bool
    response: str
    error: Optional[str] = None

class HTTP2Connection:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = None
        self.conn = None
        self.logger = logging.getLogger(__name__)

    def setup(self, test_case: Dict[str, Any]) -> None:
        """Setup and initialize HTTP/2 connection"""
        self._create_socket(test_case)
        self._setup_tls(test_case)
        self._initialize_connection(test_case)

    def _create_socket(self, test_case: Dict[str, Any]) -> None:
        self.sock = socket.create_connection((self.host, self.port))
        self.logger.info("Socket connected")

    def _setup_tls(self, test_case: Dict[str, Any]) -> None:
        """Setup TLS if enabled in test case"""
        connection_settings = test_case.get('connection_settings', {})
        if connection_settings.get('tls_enabled', False):
            self.logger.info("Setting up TLS...")
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self.sock = context.wrap_socket(self.sock)
            self.logger.info("TLS established")

    def _initialize_connection(self, test_case: Dict[str, Any]) -> None:
        """Initialize HTTP/2 connection"""
        self._apply_connection_settings(test_case.get('connection_settings', {}))
        self._send_client_preface()
        self._handle_server_preface()

    def _apply_connection_settings(self, settings: Dict[str, Any]) -> None:
        """Apply connection settings from test case"""
        config = h2.config.H2Configuration(
            client_side=settings.get('client_side', True),
            header_encoding=settings.get('header_encoding', 'utf-8')
        )
        self.conn = h2.connection.H2Connection(config=config)
        if 'settings' in settings:
            self.conn.update_settings(settings['settings'])

    def _send_client_preface(self) -> None:
        """Send HTTP/2 client preface"""
        self.logger.info("Sending client preface...")
        preface = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
        self.sock.sendall(preface)
        self.conn.initiate_connection()
        self.sock.sendall(self.conn.data_to_send())

    def _handle_server_preface(self) -> None:
        """Handle server preface and SETTINGS frame"""
        self.logger.info("Waiting for server SETTINGS...")
        data = self.sock.recv(65535)
        if not data:
            raise Exception("No server SETTINGS received")
        events = self.conn.receive_data(data)
        self.logger.info(f"Received server SETTINGS: {events}")
        self.sock.sendall(self.conn.data_to_send())

    def _format_headers(self, headers) -> List[Tuple[str, str]]:
        """Convert YAML header format to h2 format"""
        formatted_headers = []
        
        if 'pseudo_headers' in headers:
            for name, value in headers['pseudo_headers'].items():
                formatted_headers.append((f":{name}", str(value)))
        
        if 'regular_headers' in headers:
            for name, value in headers['regular_headers'].items():
                formatted_headers.append((name, str(value)))
        
        return formatted_headers

    def send_frames(self, frames: List[Dict]) -> None:
        """Send frames according to test configuration"""
        for frame in frames:
            frame_type = FrameType(frame['type'].upper())
            
            if frame_type == FrameType.SETTINGS:
                self.conn.update_settings(frame.get('settings', {}))
            elif frame_type == FrameType.PRIORITY:
                stream_id = frame.get('stream_id')
                depends_on = frame.get('depends_on', 0)
                weight = frame.get('weight', 16)
                exclusive = frame.get('exclusive', False)
                
                # If payload_length is specified, send raw frame with incorrect length
                if 'payload_length' in frame:
                    # Create a raw PRIORITY frame with incorrect length
                    frame_data = (
                        depends_on.to_bytes(4, byteorder='big') +  # 4 bytes for depends_on
                        weight.to_bytes(1, byteorder='big') +      # 1 byte for weight
                        b'\x00'  # Extra byte to make length incorrect
                    )
                    
                    # Frame header: length (3 bytes), type (1 byte), flags (1 byte), stream id (4 bytes)
                    frame_header = (
                        len(frame_data).to_bytes(3, byteorder='big') +  # Length
                        b'\x02' +  # Type (2 for PRIORITY)
                        b'\x00' +  # Flags
                        stream_id.to_bytes(4, byteorder='big')  # Stream ID
                    )
                    
                    self.sock.sendall(frame_header + frame_data)
                else:
                    # Normal PRIORITY frame
                    self.conn.prioritize(
                        stream_id=stream_id,
                        depends_on=depends_on,
                        weight=weight,
                        exclusive=exclusive
                )
        
            elif frame_type == FrameType.HEADERS:
                stream_id = frame.get('stream_id', self.conn.get_next_available_stream_id())
                end_stream = 'END_STREAM' in frame.get('flags', [])
                headers = self._format_headers(frame.get('headers'))
                self.conn.send_headers(
                    stream_id=stream_id,
                    headers=headers,
                    end_stream=end_stream
                )
            elif frame_type == FrameType.DATA:
                stream_id = frame.get('stream_id', 1)
                end_stream = 'END_STREAM' in frame.get('flags', [])
                payload_size = frame.get('payload_size', 0)
                
                # Generate dummy data of specified size
                data = b'X' * payload_size
                

                self.conn.send_data(
                    stream_id=stream_id,
                    data=data,
                    end_stream=end_stream
                )
            elif frame_type == FrameType.RST_STREAM:
                stream_id = frame.get('stream_id')
                error_code = frame.get('error_code', 'CANCEL')
                
                # If payload_length is specified, send raw frame with incorrect length
                if 'payload_length' in frame:
                    # Create a raw RST_STREAM frame with incorrect length
                    frame_data = (
                        getattr(h2.errors.ErrorCodes, error_code).to_bytes(4, byteorder='big') +  # 4 bytes for error code
                        b'\x00'  # Extra byte to make length incorrect
                    )
                    
                    # Frame header: length (3 bytes), type (1 byte), flags (1 byte), stream id (4 bytes)
                    frame_header = (
                        len(frame_data).to_bytes(3, byteorder='big') +  # Length
                        b'\x03' +  # Type (3 for RST_STREAM)
                        b'\x00' +  # Flags
                        stream_id.to_bytes(4, byteorder='big')  # Stream ID
                    )
                    
                    self.sock.sendall(frame_header + frame_data)
                else:
                    # Normal RST_STREAM frame
                    self.conn.reset_stream(stream_id, error_code=getattr(h2.errors.ErrorCodes, error_code))

            outbound_data = self.conn.data_to_send()
            if outbound_data:
                self.sock.sendall(outbound_data)

    def receive_response(self) -> str:
        """Handle server response"""
        response_data = b''
        
        while True:
            data = self.sock.recv(65535)
            if not data:
                break
                
            events = self.conn.receive_data(data)
            
            for event in events:
                if isinstance(event, h2.events.ResponseReceived):
                    self.logger.info(f"Response headers: {event.headers}")
                elif isinstance(event, h2.events.DataReceived):
                    response_data += event.data
                    self.conn.acknowledge_received_data(
                        event.flow_controlled_length, 
                        event.stream_id
                    )
                elif isinstance(event, h2.events.StreamEnded):
                    return response_data.decode('utf-8')
                    
            outbound_data = self.conn.data_to_send()
            if outbound_data:
                self.sock.sendall(outbound_data)
        
        return response_data.decode('utf-8') if response_data else ''

    def close(self) -> None:
        """Close the connection"""
        if self.sock:
            self.sock.close()

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

class HTTP2Client:
    def __init__(self, host: str = 'localhost', port: int = 7700, yaml_path: str = 'test_cases.yaml'):
        self.connection = HTTP2Connection(host, port)
        self.test_manager = TestCaseManager(yaml_path)
        self.logger = logging.getLogger(__name__)

    def run_test(self, test_id: int) -> TestResult:
        """Run a single test case"""
        try:
            test_case, suite = self.test_manager.find_test_case(test_id)
            if not test_case:
                raise ValueError(f"Test {test_id} not found")

            self.logger.info(f"Running test suite: {suite['name']}")
            self.logger.info(f"Section: {suite['section']}")
            self.logger.info(f"Description: {test_case['description']}")

            expected_response = test_case.get('expected_response', {})
            if expected_response.get('type') == 'timeout':
                self.connection.sock.settimeout(expected_response.get('duration', 5))

            self.connection.setup(test_case)
            
            try:
                response = self._execute_test(test_case)
                return TestResult(test_id, True, response)
            except socket.timeout as e:
                return self._handle_timeout(test_case, test_id, e)
            
        except Exception as e:
            self.logger.error(f"Test failed: {str(e)}", exc_info=True)
            return TestResult(test_id, False, "", str(e))
        finally:
            self.connection.close()

    def _execute_test(self, test_case: Dict[str, Any]) -> str:
        """Execute the test case and return the response"""
        if 'client_frames' in test_case:
            self.connection.send_frames(test_case['client_frames'])
        
        return self.connection.receive_response()

    def _handle_timeout(self, test_case: Dict[str, Any], test_id: int, error: socket.timeout) -> TestResult:
        """Handle timeout scenarios"""
        expected_response = test_case.get('expected_response', {})
        if expected_response.get('type') == 'timeout':
            return TestResult(test_id, True, "Timeout as expected")
        return TestResult(test_id, False, "", f"Unexpected timeout: {str(error)}")

def main():
    client = HTTP2Client()
    try:
        test_id = 8
        result = client.run_test(test_id)
        print(f"\nTest {'PASSED' if result.success else 'FAILED'}")
        if result.error:
            print(f"Error: {result.error}")
        print(f"Response: {result.response}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()