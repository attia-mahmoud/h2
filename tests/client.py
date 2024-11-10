import h2.connection
import h2.events
import h2.config
import socket
import yaml
import sys
from typing import List, Tuple, Dict, Optional

class HTTP2Client:
    def __init__(self, host: str = 'localhost', port: int = 7700, yaml_path: str = 'test_cases.yaml'):
        self.host = host
        self.port = port
        self.yaml_path = yaml_path
        self.sock = None
        self.conn = None
        
    def _load_test_headers(self, test_id: int) -> List[Tuple[str, str]]:
        try:
            with open(self.yaml_path, 'r') as f:
                test_data = yaml.safe_load(f)
                test_case = self._find_test_case(test_data, test_id)
                
                if test_case is None:
                    raise ValueError(f"Test {test_id} not found")
                
                # Print test information
                suite = self._find_test_suite(test_data, test_id)
                print(f"\nRunning test suite: {suite['name']}")
                print(f"Section: {suite['section']}")
                print(f"Description: {test_case['description']}")
                
                # Convert headers to h2 format
                return self._format_headers(test_case['headers'])
                
        except FileNotFoundError:
            raise FileNotFoundError(f"{self.yaml_path} not found")
        except yaml.YAMLError:
            raise ValueError(f"Invalid YAML in {self.yaml_path}")

    def _find_test_case(self, test_data: Dict, test_id: int) -> Optional[Dict]:
        """Find a test case by ID across all test suites"""
        for suite in test_data['test_suites']:
            for case in suite['cases']:
                if case['id'] == test_id:
                    return case
        return None

    def _find_test_suite(self, test_data: Dict, test_id: int) -> Optional[Dict]:
        """Find the test suite containing a specific test ID"""
        for suite in test_data['test_suites']:
            if any(case['id'] == test_id for case in suite['cases']):
                return suite
        return None

    def _format_headers(self, headers: Dict) -> List[Tuple[str, str]]:
        """Convert YAML header format to h2 format"""
        formatted_headers = []
        
        # Add pseudo-headers first (with : prefix)
        for name, value in headers['pseudo_headers'].items():
            formatted_headers.append((f":{name}", str(value)))
            
        # Add regular headers
        for name, value in headers['regular_headers'].items():
            formatted_headers.append((name, str(value)))
            
        # Handle duplicate pseudo-headers if present
        if 'duplicate_pseudo_headers' in headers:
            for name, value in headers['duplicate_pseudo_headers'].items():
                formatted_headers.append((f":{name}", str(value)))
                
        return formatted_headers

    def _setup_connection(self) -> None:
        self.sock = socket.create_connection((self.host, self.port))
        config = h2.config.H2Configuration(client_side=True)
        self.conn = h2.connection.H2Connection(config=config)
        
        self.conn.initiate_connection()
        self.sock.sendall(self.conn.data_to_send())
        print(f"Connected to server at {self.host}:{self.port}")

    def _send_request(self, headers: List[Tuple[str, str]]) -> int:
        stream_id = self.conn.get_next_available_stream_id()
        self.conn.send_headers(stream_id, headers, end_stream=True)
        self.sock.sendall(self.conn.data_to_send())
        return stream_id

    def _handle_response(self) -> str:
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

    def make_request(self, test_id: int) -> str:
        try:
            headers = self._load_test_headers(test_id)
            self._setup_connection()
            self._send_request(headers)
            return self._handle_response()
        except Exception as e:
            print(f"Error during request: {e}")
            raise
        finally:
            if self.sock:
                self.sock.close()

def main():
    client = HTTP2Client()
    try:
        response = client.make_request(147)  # Example test ID
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()