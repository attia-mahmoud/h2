import h2.connection
import h2.events
import h2.config
import h2.settings
import socket
import yaml
import sys
import time
from typing import List, Tuple, Dict, Optional, Any
from enum import Enum
import ssl

class TestResult:
    def __init__(self, test_id: int, success: bool, response: str, error: Optional[str] = None):
        self.test_id = test_id
        self.success = success
        self.response = response
        self.error = error

class HTTP2Client:
    def __init__(self, host: str = 'localhost', port: int = 7700, yaml_path: str = 'test_cases.yaml'):
        self.host = host
        self.port = port
        self.yaml_path = yaml_path
        self.sock = None
        self.conn = None
        self.test_data = self._load_yaml()
        
    def _load_yaml(self) -> Dict:
        """Load and parse YAML test configuration"""
        try:
            with open(self.yaml_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"{self.yaml_path} not found")
        except yaml.YAMLError:
            raise ValueError(f"Invalid YAML in {self.yaml_path}")

    def _find_test_case(self, test_id: int) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Find test case and its parent suite by ID"""
        for suite in self.test_data['test_suites']:
            for case in suite['cases']:
                if case['id'] == test_id:
                    return case, suite
        return None, None

    def _apply_connection_settings(self, settings: Dict[str, Any]) -> None:
        """Apply connection settings from test case"""
        config = h2.config.H2Configuration(
            client_side=settings.get('client_side', True),
            header_encoding=settings.get('header_encoding', 'utf-8')
        )
        
        self.conn = h2.connection.H2Connection(config=config)
        
        # Apply any custom settings
        if 'settings' in settings:
            self.conn.update_settings(settings['settings'])

    def _format_headers(self, headers: Dict) -> List[Tuple[str, str]]:
        """Convert YAML header format to h2 format"""
        formatted_headers = []
        
        # Add pseudo-headers first
        if 'pseudo_headers' in headers:
            for name, value in headers['pseudo_headers'].items():
                formatted_headers.append((f":{name}", str(value)))
        
        # Add regular headers
        if 'regular_headers' in headers:
            for name, value in headers['regular_headers'].items():
                formatted_headers.append((name, str(value)))
        
        return formatted_headers

    def _setup_connection(self, test_case: Dict) -> None:
        """Setup connection based on test configuration"""
        print("Setting up client connection...")
        
        # Create basic socket
        self.sock = socket.create_connection((self.host, self.port))
        print("Socket connected")
        
        # Handle TLS if enabled
        if test_case.get('connection_settings', {}).get('tls_enabled'):
            print("Setting up TLS...")
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self.sock = context.wrap_socket(self.sock)
            print("TLS established")
    
        # Apply connection settings
        self._apply_connection_settings(test_case.get('connection_settings', {}))
        
        # Send client preface
        print("Sending client preface...")
        preface = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
        self.sock.sendall(preface)
        
        # Send initial SETTINGS
        print("Sending initial SETTINGS...")
        self.conn.initiate_connection()
        self.sock.sendall(self.conn.data_to_send())
        
        # Receive server preface (SETTINGS frame)
        print("Waiting for server SETTINGS...")
        data = self.sock.recv(65535)
        if not data:
            raise Exception("No server SETTINGS received")
        events = self.conn.receive_data(data)
        print(f"Received server SETTINGS: {events}")
        
        # Send SETTINGS ACK
        print("Sending SETTINGS ACK...")
        self.sock.sendall(self.conn.data_to_send())
        
        # Format and send headers
        print("Sending request headers...")
        headers = self._format_headers(test_case['headers'])
        stream_id = self.conn.get_next_available_stream_id()
        self.conn.send_headers(
            stream_id=stream_id,
            headers=headers,
            end_stream=True
        )
        self.sock.sendall(self.conn.data_to_send())
        print(f"Request sent on stream {stream_id}")

    def _send_frames(self, frames: List[Dict]) -> None:
        """Send frames according to test configuration"""
        for frame in frames:
            frame_type = frame['type'].upper()
            
            if frame_type == 'HEADERS':
                stream_id = frame.get('stream_id', self.conn.get_next_available_stream_id())
                end_stream = 'END_STREAM' in frame.get('flags', [])
                
                # The h2 library uses end_stream parameter, not end_headers
                self.conn.send_headers(
                    stream_id=stream_id,
                    headers=self._current_headers,
                    end_stream=end_stream
                )
            
            elif frame_type == 'SETTINGS':
                self.conn.update_settings(frame.get('settings', {}))
            
            # Add more frame types as needed
            
            self.sock.sendall(self.conn.data_to_send())

    def _handle_response(self) -> str:
        """Handle server response"""
        response_data = b''
        
        while True:
            data = self.sock.recv(65535)
            if not data:
                break
                
            events = self.conn.receive_data(data)
            
            for event in events:
                if isinstance(event, h2.events.ResponseReceived):
                    print(f"Response headers: {event.headers}")
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

    def run_test(self, test_id: int) -> TestResult:
        """Run a single test case"""
        try:
            # Find test case
            test_case, suite = self._find_test_case(test_id)
            if not test_case:
                raise ValueError(f"Test {test_id} not found")

            # Print test information
            print(f"\nRunning test suite: {suite['name']}")
            print(f"Section: {suite['section']}")
            print(f"Description: {test_case['description']}")

            expected_response = test_case.get('expected_response', {})
            
            # If timeout is expected, set socket timeout
            if expected_response.get('type') == 'timeout':
                timeout_duration = expected_response.get('duration', 5)
                if self.sock:
                    self.sock.settimeout(timeout_duration)

            # Setup connection
            self._setup_connection(test_case)
            
            # Format headers
            self._current_headers = self._format_headers(test_case['headers'])
            
            try:
                # Send frames
                if 'frames' in test_case:
                    self._send_frames(test_case['frames'])
                
                # Get response
                response = self._handle_response()
                
            except socket.timeout:
                # If timeout was expected, this is a success
                if expected_response.get('type') == 'timeout':
                    return TestResult(test_id, True, "Timeout as expected")
                else:
                    return TestResult(test_id, False, "", "Unexpected timeout")
            
            return TestResult(test_id, True, response)
            
        except Exception as e:
            return TestResult(test_id, False, "", str(e))
        finally:
            if self.sock:
                self.sock.close()

def main():
    client = HTTP2Client()
    try:
        result = client.run_test(2)  # test ID
        print(f"\nTest {'PASSED' if result.success else 'FAILED'}")
        if result.error:
            print(f"Error: {result.error}")
        print(f"Response: {result.response}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()