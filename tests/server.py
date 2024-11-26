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
import time

logger = setup_logging(__name__)

FRAME_TIMEOUT_SECONDS = 1  # Timeout when waiting for frames

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
            ServerState.WAITING_ACK: self._handle_waiting_ack,
            ServerState.RECEIVING_FRAMES: self._handle_receiving_frames,
            ServerState.SENDING_FRAMES: self._handle_sending_frames,
            ServerState.CLOSING: self._handle_closing
        }

    def _transition_to(self, new_state: ServerState):
        """Safely transition to a new state"""
        logger.debug(f"State transition: {self.state} -> {new_state}")
        self.state = new_state

    def _handle_frame(self, event: h2.events.Event, client_socket: ssl.SSLSocket) -> None:
        log_h2_frame(logger, "RECEIVED", event)
        """Central event handler that updates state based on received events"""
        if isinstance(event, h2.events.RemoteSettingsChanged):
            if self.state == ServerState.WAITING_PREFACE:
                outbound_data = self.conn.data_to_send()  # This will generate SETTINGS ACK
                if outbound_data:
                    client_socket.sendall(outbound_data)
                self._transition_to(ServerState.WAITING_ACK)
        
        elif isinstance(event, h2.events.SettingsAcknowledged):
            if self.state == ServerState.WAITING_ACK:
                self._transition_to(ServerState.RECEIVING_FRAMES)
        
        elif isinstance(event, h2.events.ConnectionTerminated):
            logger.info(f"Received GOAWAY frame. Error code: {event.error_code}")
            self._transition_to(ServerState.CLOSING)


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
        
        # Send connection preface
        self.conn.initiate_connection()
        client_socket.sendall(self.conn.data_to_send())
        self._transition_to(ServerState.WAITING_PREFACE)

    def _handle_waiting_preface(self, client_socket: ssl.SSLSocket):
        """Wait for client's connection preface"""
        data = self._receive_frame(client_socket)
        if data:
            events = self.conn.receive_data(data)
            for event in events:
                self._handle_frame(event, client_socket)

    def _handle_waiting_ack(self, client_socket: ssl.SSLSocket):
        """Wait for server's SETTINGS_ACK frame"""
        data = self._receive_frame(client_socket)
        if data:
            events = self.conn.receive_data(data)
            for event in events:
                self._handle_frame(event, client_socket)

    def _handle_receiving_frames(self, client_socket: ssl.SSLSocket):
        """Handle response waiting state."""
        expected_client_frames = len(self.test_case.get('client_frames', []))
        
        # If we don't expect any frames from client, skip waiting
        if expected_client_frames == 0:
            logger.info("No client frames expected, sending frames")
            self._transition_to(ServerState.SENDING_FRAMES)
            return
        
        for i in range(expected_client_frames):
            data = self._receive_frame(client_socket)
            if data is None:  # Timeout occurred
                logger.info("Timeout waiting for client frames, sending frames")
                self._transition_to(ServerState.SENDING_FRAMES)
                return
            
            else:
                events = self.conn.receive_data(data)
                for event in events:
                    self._handle_frame(event, client_socket)
                
                outbound_data = self.conn.data_to_send()
                if outbound_data:
                    client_socket.sendall(outbound_data)
                    
    def _handle_sending_frames(self, client_socket: ssl.SSLSocket):
        """Send frames based on test case"""
        if self.state != ServerState.SENDING_FRAMES:
            raise RuntimeError(f"Cannot send frames in state {self.state}")
        
        try:
            frames = self.test_case.get('server_frames', [])
            
            for i, frame in enumerate(frames):
                logger.info(f"Sending frame {i+1}/{len(frames)}: {frame.get('type')}")
                send_frame(self.conn, client_socket, frame, self.test_case['id'])
            
            # Add a small delay to ensure frames are transmitted
            time.sleep(0.1)
            
            # Wait for any client frames
            self._transition_to(ServerState.RECEIVING_FRAMES)

        except Exception as e:
            logger.error(f"Error sending frames: {e}")
            raise

    def _handle_closing(self, client_socket: ssl.SSLSocket):
        """Close the connection"""
        client_socket.close()
        self._transition_to(ServerState.CLOSED)

    def _receive_frame(self, client_socket: ssl.SSLSocket, timeout: float = FRAME_TIMEOUT_SECONDS) -> bytes:
        """Helper method to receive data with timeout"""
        client_socket.settimeout(timeout)
        try:
            data = client_socket.recv(SSL_CONFIG.MAX_BUFFER_SIZE)
            if not data:
                logger.warning(f"No data received after {timeout}s in state {self.state}")
                # self._transition_to(ServerState.CLOSING)
            return data
        except socket.timeout:
            logger.warning(f"Timeout waiting for frame in state {self.state}")
            # self._transition_to(ServerState.CLOSING)
            return None
        except (ConnectionResetError, BrokenPipeError):
            logger.warning("Connection closed by peer")
            # self._transition_to(ServerState.CLOSING)
            return None

    def handle_connection(self, client_socket: ssl.SSLSocket):
        """Main connection loop"""
        try:
            while self.state != ServerState.CLOSED:
                handler = self._state_handlers.get(self.state)
                if handler:
                    handler(client_socket)
                else:
                    raise RuntimeError(f"No handler for state {self.state}")
                
        except Exception as e:
            handle_socket_error(logger, e, "connect")
            self._transition_to(ServerState.CLOSING)  # Instead of calling close()

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
        except Exception as e:
            handle_socket_error(logger, e, "start")

def main():
    parser = argparse.ArgumentParser(description='HTTP/2 Server')
    parser.add_argument('--test-id', type=int, help='Test case ID to run')
    args = parser.parse_args()

    server = HTTP2Server(test_case=load_test_case(logger, args.test_id))
    server.start()

if __name__ == '__main__':
    main()