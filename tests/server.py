import h2.connection
import h2.config
import h2.events
import socket
import select
import yaml
import ssl
from typing import List, Tuple, Dict, Optional, Any
import sys

class HTTP2Server:
    def __init__(self, host: str = 'localhost', port: int = 7700, yaml_path: str = 'test_cases.yaml'):
        self.host = host
        self.port = port
        self.sock = None
        self.yaml_path = yaml_path
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
        
    def _create_response_headers(self, stream_id: int) -> List[Tuple[str, str]]:
        return [
            (':status', '200'),
            ('content-type', 'text/plain'),
            ('content-length', str(len('Hello, World!')))
        ]

    def _setup_socket(self, test_id: int) -> None:
        test_case, suite = self._find_test_case(test_id)
        if not test_case:
            raise ValueError(f"Test {test_id} not found")

        print(f"\nRunning test suite: {suite['name']}")
        print(f"Section: {suite['section']}")
        print(f"Description: {test_case['description']}")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Setup TLS if specified in test case
        connection_settings = test_case.get('connection_settings', {})
        if connection_settings.get('tls_enabled', False):
            print("Setting up TLS...")
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(certfile="certs/server.crt", keyfile="certs/server.key")
            self.sock = context.wrap_socket(self.sock, server_side=True)
            print("TLS established")
        
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.sock.settimeout(10)

    def _handle_request(self, event: h2.events.RequestReceived, 
                       conn: h2.connection.H2Connection,
                       client_socket: socket.socket) -> None:
        print(f"Request headers: {event.headers}")
        
        # Send response headers
        conn.send_headers(
            stream_id=event.stream_id,
            headers=self._create_response_headers(event.stream_id),
            end_stream=False
        )
        
        # Send response data
        response_data = 'Hello, World!'.encode('utf-8')
        conn.send_data(
            stream_id=event.stream_id,
            data=response_data,
            end_stream=True
        )
        
        client_socket.sendall(conn.data_to_send())

    def _handle_client(self, client_socket: socket.socket, addr: Tuple[str, int]) -> None:
        print(f"Connection from {addr}")
        
        try:
            # Initialize connection
            config = h2.config.H2Configuration(client_side=False)
            conn = h2.connection.H2Connection(config=config)
            
            # Wait for client preface
            print("Waiting for client preface...")
            preface = client_socket.recv(24)
            if preface != b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n':
                print(f"Invalid client preface: {preface}")
                return
            print("Valid client preface received")
            
            # Send server preface (SETTINGS frame)
            print("Sending server preface and SETTINGS...")
            conn.initiate_connection()
            client_socket.sendall(conn.data_to_send())
            
            # Receive client SETTINGS
            print("Waiting for client SETTINGS...")
            data = client_socket.recv(65535)
            events = conn.receive_data(data)
            print(f"Received client SETTINGS: {events}")
            
            # Send SETTINGS ACK
            outbound_data = conn.data_to_send()
            if outbound_data:
                client_socket.sendall(outbound_data)
            
            # Now wait for the actual request
            print("Waiting for request...")
            while True:
                data = client_socket.recv(65535)
                if not data:
                    print("Connection closed by client")
                    break
                
                events = conn.receive_data(data)
                print(f"Received events: {events}")
                
                for event in events:
                    if isinstance(event, h2.events.RequestReceived):
                        print("Request received, sending response...")
                        self._handle_request(event, conn, client_socket)
                        return  # Exit after handling one request
                
                outbound_data = conn.data_to_send()
                if outbound_data:
                    client_socket.sendall(outbound_data)
                    
        except Exception as e:
            print(f"Error handling client: {e}")
            import traceback
            traceback.print_exc()
        finally:
            client_socket.close()
            print("Connection closed")

    def run(self, test_id: int) -> None:
        self._setup_socket(test_id)
        print(f"Server listening on {self.host}:{self.port}")
        
        try:
            while True:
                client_socket, addr = self.sock.accept()
                self._handle_client(client_socket, addr)
                break
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            if self.sock:
                self.sock.close()

def main():
    try:
        test_id = 2
        server = HTTP2Server()
        server.run(test_id)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()