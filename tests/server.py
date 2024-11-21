import overload
import h2.config
import h2.connection
import h2.events
import ssl
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

logger = setup_logging(__name__)

class HTTP2Server:
    def __init__(self, host: str = 'localhost', port: int = 8443, test_case: dict = None):
        self.host = host
        self.port = port
        self.sock = None
        self.conn = None
        self.test_case = test_case
        
    def start(self):
        """Start the HTTP/2 server"""
        try:
            # Create and configure socket
            self.sock = create_socket(self.host, self.port, is_server=True)
            self.sock.listen(5)
                        
            while True:
                try:
                    client_socket, address = self.sock.accept()
                    logger.info(f"Connection from {address}")
                    
                    self.handle_connection(client_socket)
                    
                except KeyboardInterrupt:
                    logger.info("Shutting down server...")
                    break
                except Exception as e:
                    handle_socket_error(logger, e, "connection handling")
                finally:
                    if client_socket:
                        client_socket.close()
                        
        finally:
            if self.sock:
                self.sock.close()
    
    def handle_connection(self, client_socket: ssl.SSLSocket):
        """Handle a single client connection"""
        try:
            # Get TLS setting from test case, default to False
            tls_enabled = self.test_case.get('tls_enabled', False)
            
            if tls_enabled:
                ssl_context = create_ssl_context(self.test_case, is_client=False)
                client_socket = ssl_context.wrap_socket(
                    client_socket,
                    server_side=True
                )
            
            config_settings = CONFIG_SETTINGS.copy()
            config_settings.update(self.test_case.get('connection_settings_server', {}))
            config = h2.config.H2Configuration(client_side=False, **config_settings)
            self.conn = h2.connection.H2Connection(config=config)
            self.conn.initiate_connection()
            
            client_socket.sendall(self.conn.data_to_send())
            
            # If there are no client frames, send server frames immediately
            if not self.test_case.get('client_frames'):
                for frame in self.test_case.get('server_frames', []):
                    send_frame(self.conn, client_socket, frame, self.test_case['id'])
            
            while not self.conn.state_machine.state == h2.connection.ConnectionState.CLOSED:
                data = client_socket.recv(SSL_CONFIG.MAX_BUFFER_SIZE)
                if not data:
                    break
                
                # Log received preface if this is the first data
                if data.startswith(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'):
                    logger.info("\n" + "="*50)
                    logger.info("RECEIVED HTTP/2 PREFACE")
                    logger.info("="*50)
                
                events = self.conn.receive_data(data)
                # settings_changed = 0
                for event in events:
                    # Log all events
                    log_h2_frame(logger, "RECEIVED", event)

                    # if isinstance(event, h2.events.RemoteSettingsChanged):
                    #     settings_changed += 1
                    #     if settings_changed > 1:
                    #         self.handle_event(event, client_socket)
                    # else:
                    #     self.handle_event(event, client_socket)
                    self.handle_event(event, client_socket)
                    
                outbound_data = self.conn.data_to_send()
                if outbound_data:
                    client_socket.sendall(outbound_data)
                    
        except Exception as e:
            handle_socket_error(logger, e, "connection handler")
    
    def handle_event(self, event: h2.events.Event, client_socket: ssl.SSLSocket):
        """Handle H2 events"""
        try:
            if isinstance(event, h2.events.ConnectionTerminated):
                logger.info(f"Received GOAWAY frame. Error code: {event.error_code}, "
                       f"Last Stream ID: {event.last_stream_id}")
                return
            
            if isinstance(event, h2.events.StreamEnded) or isinstance(event, h2.events.StreamReset):
                if not self.conn.state_machine.state == h2.connection.ConnectionState.CLOSED:
                    for frame in self.test_case.get('server_frames', []):
                        send_frame(self.conn, client_socket, frame, self.test_case['id'])
                        
        except Exception as e:
            handle_socket_error(logger, e, "handle_event")

def main():
    parser = argparse.ArgumentParser(description='HTTP/2 Server')
    parser.add_argument('--test-id', type=int, help='Test case ID to run')
    args = parser.parse_args()


    server = HTTP2Server(test_case=load_test_case(logger, args.test_id))
        
    server.start()

if __name__ == '__main__':
    main()