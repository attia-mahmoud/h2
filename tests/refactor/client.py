import h2.connection
import h2.config
import h2.events
from utils import (
    setup_logging,
    create_ssl_context,
    create_socket,
    handle_socket_error,
    SSL_CONFIG,
    log_h2_frame,
    load_test_case,
    CONFIG_SETTINGS,
    send_frame
)
import argparse
import socket

logger = setup_logging('client')

class HTTP2Client:
    def __init__(self, host: str = 'localhost', port: int = 8443, test_case: dict = None):
        self.host = host
        self.port = port
        self.sock = None
        self.conn = None
        self.test_case = test_case
        
    def connect(self):
        """Establish HTTP/2 connection with server"""
        try:
            # Create and configure socket
            self.sock = create_socket(self.host, self.port)
            
            # Get TLS setting from test case, default to False
            tls_enabled = self.test_case.get('tls_enabled', False)
            
            if tls_enabled:
                self.sock = create_ssl_context(is_client=True).wrap_socket(
                    self.sock,
                    server_hostname=self.host
                )
            
            self.sock.connect((self.host, self.port))

            config_settings = CONFIG_SETTINGS.copy()
            config_settings.update(self.test_case.get('connection_settings', {}))
            
            # Initialize H2 connection
            config = h2.config.H2Configuration(client_side=True, **config_settings)
            self.conn = h2.connection.H2Connection(config=config)
            self.conn.initiate_connection()
            
            # Send initial data
            self.sock.sendall(self.conn.data_to_send())
        except Exception as e:
            handle_socket_error(logger, e, "connect")
        
    def send_frames(self):
        """Send all frames specified in the test case and handle responses"""
        for frame in self.test_case['client_frames']:
            send_frame(self.conn, self.sock, frame, logger)
            
            # Check for server responses after sending each frame
            self._receive_response()

    def _receive_response(self, timeout: float = 0.1) -> str:
        """Process and return response
        Args:
            timeout: How long to wait for a response in seconds
        """
        response_data = b''
        
        # Set socket to non-blocking with timeout
        self.sock.settimeout(timeout)
        
        try:
            data = self.sock.recv(SSL_CONFIG.MAX_BUFFER_SIZE)
            if data:
                events = self.conn.receive_data(data)
                for event in events:
                    # Log all events
                    log_h2_frame(logger, "RECEIVED", event)
                    
                    if isinstance(event, h2.events.DataReceived):
                        response_data += event.data
                        self.conn.acknowledge_received_data(
                            event.flow_controlled_length, 
                            event.stream_id
                        )
                    elif isinstance(event, h2.events.StreamEnded):
                        return response_data.decode()
                
                outbound_data = self.conn.data_to_send()
                if outbound_data:
                    self.sock.sendall(outbound_data)
        except socket.timeout:
            # No data received within timeout period
            logger.debug("No response received within timeout")
        except BlockingIOError:
            # No data available to read at the moment
            logger.debug("No data available to read")
        
        return response_data.decode() if response_data else ""
    
    def close(self):
        """Close the connection"""
        if self.sock:
            self.sock.close()

def main():
    parser = argparse.ArgumentParser(description='HTTP/2 Client')
    parser.add_argument('--test-id', type=int, help='Test case ID to run')
    args = parser.parse_args()

    client = HTTP2Client(test_case=load_test_case(logger, args.test_id))
        
    try:
        client.connect()
        client.send_frames()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        client.close()

if __name__ == '__main__':
    main()