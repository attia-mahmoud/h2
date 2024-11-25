import socket
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
from states import ServerState

logger = setup_logging(__name__)

FRAME_TIMEOUT_SECONDS = 5  # Timeout when waiting for frames

class HTTP2Server:
    def __init__(self, host: str = 'localhost', port: int = 8443, test_case: dict = None):
        self.host = host
        self.port = port
        self.sock = None
        self.conn = None
        self.test_case = test_case
        self.state = ServerState.IDLE
        self._state_handlers = {
            ServerState.IDLE: self._handle_idle,
            ServerState.WAITING_PREFACE: self._handle_waiting_preface,
            ServerState.PREFACE_RECEIVED: self._handle_preface_received,
            ServerState.SETTINGS_ACKED: self._handle_settings_acked,
            ServerState.RECEIVING_FRAMES: self._handle_receiving_frames,
        }

    def _transition_to(self, new_state: ServerState):
        """Safely transition to a new state"""
        logger.debug(f"State transition: {self.state} -> {new_state}")
        self.state = new_state

    def _handle_event(self, event: h2.events.Event, client_socket: ssl.SSLSocket) -> None:
        """Central event handler that updates state based on received events"""
        log_h2_frame(logger, "RECEIVED", event)

        if isinstance(event, h2.events.RemoteSettingsChanged):
            # When we receive client's SETTINGS, we need to acknowledge it
            outbound_data = self.conn.data_to_send()  # This will generate SETTINGS ACK
            if outbound_data:
                client_socket.sendall(outbound_data)
        
        elif isinstance(event, h2.events.SettingsAcknowledged):
            if self.state == ServerState.PREFACE_RECEIVED:
                self._transition_to(ServerState.SETTINGS_ACKED)
        
        elif isinstance(event, h2.events.ConnectionTerminated):
            logger.info(f"Received GOAWAY frame. Error code: {event.error_code}")
            self._transition_to(ServerState.CLOSING)
            
        elif isinstance(event, (h2.events.StreamEnded, h2.events.StreamReset)):
            if not self.conn.state_machine.state == h2.connection.ConnectionState.CLOSED:
                if self.test_case.get('server_frames', None):
                    self._transition_to(ServerState.SENDING_FRAMES)
                    for frame in self.test_case['server_frames']:
                        send_frame(self.conn, client_socket, frame, self.test_case['id'])
                    self._transition_to(ServerState.RECEIVING_FRAMES)


    def _handle_idle(self, client_socket: ssl.SSLSocket):
        """Initialize connection settings"""
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
        
        # Send initial SETTINGS frame
        self.conn.initiate_connection()
        client_socket.sendall(self.conn.data_to_send())
        self._transition_to(ServerState.WAITING_PREFACE)

    def _handle_waiting_preface(self, client_socket: ssl.SSLSocket):
        """Wait for client's connection preface"""
        data = self._receive_data(client_socket)
        if not data:
            return

        if data.startswith(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'):
            logger.info("Received HTTP/2 preface")
            self._transition_to(ServerState.PREFACE_RECEIVED)
            
            # Process the rest of the data (which should include client's SETTINGS)
            events = self.conn.receive_data(data)
            for event in events:
                self._handle_event(event, client_socket)
            
            # Send any pending data (like SETTINGS ACK)
            outbound_data = self.conn.data_to_send()
            if outbound_data:
                client_socket.sendall(outbound_data)

    def _handle_preface_received(self, client_socket: ssl.SSLSocket):
        """Process frames after receiving preface"""
        data = self._receive_data(client_socket)
        if data:
            events = self.conn.receive_data(data)
            for event in events:
                self._handle_event(event, client_socket)

    def _handle_settings_acked(self, client_socket: ssl.SSLSocket):
        """Handle the state after settings are acknowledged"""
        self._transition_to(ServerState.RECEIVING_FRAMES)

    def _handle_receiving_frames(self, client_socket: ssl.SSLSocket):
        """Process incoming frames in normal operation"""
        data = self._receive_data(client_socket)
        if data:
            events = self.conn.receive_data(data)
            for event in events:
                self._handle_event(event, client_socket)
            
            outbound_data = self.conn.data_to_send()
            if outbound_data:
                client_socket.sendall(outbound_data)

    def _receive_data(self, client_socket: ssl.SSLSocket, timeout: float = FRAME_TIMEOUT_SECONDS) -> bytes:
        """Helper method to receive data with timeout"""
        client_socket.settimeout(timeout)
        try:
            data = client_socket.recv(SSL_CONFIG.MAX_BUFFER_SIZE)
            if not data:
                logger.warning(f"No data received after {timeout}s in state {self.state}")
                self._transition_to(ServerState.CLOSING)
            return data
        except socket.timeout:
            logger.warning(f"Timeout waiting for frame in state {self.state}")
            self._transition_to(ServerState.CLOSING)
            return None
        except (ConnectionResetError, BrokenPipeError):
            logger.warning("Connection closed by peer")
            self._transition_to(ServerState.CLOSING)
            return None

    def handle_connection(self, client_socket: ssl.SSLSocket):
        """Main connection handling loop"""
        try:
            self._handle_idle(client_socket)
            
            while not self.conn.state_machine.state == h2.connection.ConnectionState.CLOSED:
                handler = self._state_handlers.get(self.state)
                if handler:
                    handler(client_socket)
                else:
                    raise RuntimeError(f"No handler for state {self.state}")
                
                if self.state == ServerState.CLOSING:
                    break
                    
        except Exception as e:
            handle_socket_error(logger, e, "connection handler")
        finally:
            self._transition_to(ServerState.CLOSED)

    def start(self):
        """Start the HTTP/2 server"""
        try:
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

def main():
    parser = argparse.ArgumentParser(description='HTTP/2 Server')
    parser.add_argument('--test-id', type=int, help='Test case ID to run')
    args = parser.parse_args()

    server = HTTP2Server(test_case=load_test_case(logger, args.test_id))
    server.start()

if __name__ == '__main__':
    main()