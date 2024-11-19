import h2.connection
import h2.config
import h2.events
from utils import (
    setup_logging,
    create_ssl_context,
    create_socket,
    format_headers,
    handle_socket_error,
    SSL_CONFIG,
    log_h2_frame
)

logger = setup_logging('client')

class HTTP2Client:
    def __init__(self, host: str = 'localhost', port: int = 8443):
        self.host = host
        self.port = port
        self.sock = None
        self.conn = None
        
    def connect(self):
        """Establish HTTP/2 connection with server"""
        try:
            # Create and configure socket
            self.sock = create_socket(self.host, self.port)
            self.sock = create_ssl_context(is_client=True).wrap_socket(
                self.sock,
                server_hostname=self.host
            )
            self.sock.connect((self.host, self.port))
            
            # Initialize H2 connection
            config = h2.config.H2Configuration(client_side=True, incorrect_connection_preface=True)
            self.conn = h2.connection.H2Connection(config=config)
            self.conn.initiate_connection()
            
            # Send initial data
            self.sock.sendall(self.conn.data_to_send())
        except Exception as e:
            handle_socket_error(logger, e, "connect")
        
    def send_request(self, path: str = '/') -> str:
        """Send HTTP/2 request and return response"""
        request_headers = [
            (':method', 'GET'),
            (':path', path),
            (':authority', f'{self.host}:{self.port}'),
            (':scheme', 'https'),
            ('user-agent', 'basic-h2-client'),
        ]
        
        stream_id = self.conn.get_next_available_stream_id()
        self.conn.send_headers(stream_id, request_headers, end_stream=True)
        self.sock.sendall(self.conn.data_to_send())
        
        return self._receive_response()
    
    def _receive_response(self) -> str:
        """Process and return response"""
        response_data = b''
        
        while True:
            data = self.sock.recv(SSL_CONFIG.MAX_BUFFER_SIZE)
            if not data:
                break
                
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
    
    def close(self):
        """Close the connection"""
        if self.sock:
            self.sock.close()

def main():
    client = HTTP2Client()
    try:
        client.connect()
        response = client.send_request('/')
        logger.info(f"Response: {response}")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        client.close()

if __name__ == '__main__':
    main()