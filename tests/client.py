import overload
import h2.connection
import h2.config
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
import socket
import time
from states import ClientState
from checks import function_map

logger = setup_logging('client')

# Add at the top with other constants
FRAME_TIMEOUT_SECONDS = 2  # Increased from 1 to 2 seconds
MAX_RETRY_ATTEMPTS = 3

class HTTP2Client:
    def __init__(self, host: str = 'localhost', port: int = 8443, test_case: dict = None):
        self.host = host
        self.port = port
        self.sock = None
        self.conn = None
        self.test_case = test_case
        self.state = ClientState.IDLE
        
        self._state_handlers = {
            ClientState.IDLE: self._handle_idle,
            ClientState.WAITING_PREFACE: self._handle_waiting_preface,
            ClientState.WAITING_ACK: self._handle_waiting_ack,
            ClientState.SENDING_FRAMES: self._handle_sending_frames,
            ClientState.RECEIVING_FRAMES: self._handle_receiving_frames,
            ClientState.CLOSING: self._handle_closing
        }
        
    def _transition_to(self, new_state: ClientState):
        """Safely transition to a new state"""
        logger.debug(f"State transition: {self.state} -> {new_state}")
        self.state = new_state

    def _handle_frame(self, event: h2.events.Event, client_socket: ssl.SSLSocket = None) -> None:
        """Central event handler that updates state based on received events"""
        if self.state == ClientState.RECEIVING_FRAMES:
            frame_index = getattr(self, '_received_frame_count', 0)
            if frame_index < len(self.test_case.get('server_frames', [])):
                self._handle_test(event, self.test_case['server_frames'][frame_index])
        
        if isinstance(event, h2.events.RemoteSettingsChanged):
            if self.state == ClientState.WAITING_PREFACE:
                outbound_data = self.conn.data_to_send()  # This will generate SETTINGS ACK
                if outbound_data:
                    self.sock.sendall(outbound_data)
                self._transition_to(ClientState.WAITING_ACK)
            
        elif isinstance(event, h2.events.SettingsAcknowledged):
            if self.state == ClientState.WAITING_ACK:
                self._transition_to(ClientState.SENDING_FRAMES)
        
        elif isinstance(event, h2.events.ConnectionTerminated):
            logger.info(f"Received GOAWAY frame. Error code: {event.error_code}")
            self._transition_to(ClientState.CLOSING)

    def _handle_test(self, event, frame):
        """
        Handle test cases for received frames.
        Each frame can have multiple tests, where each test contains multiple checks.
        A test passes if all its checks pass.
        We try each test until one passes completely, or all tests fail.
        """
        tests = frame.get('tests', [])

        if not tests:
            logger.warning("No tests found for this frame")
            return
        
        for test_index, test in enumerate(tests, 1):
            logger.info(f"Trying test {test_index}/{len(tests)}")
            all_checks_passed = True
            
            # Try all checks in this test
            for check in test:
                function_name = check['function']
                params = check['params']
                
                function = function_map.get(function_name)
                if not function:
                    logger.warning(f"Function {function_name} not found")
                    all_checks_passed = False
                    break
                
                if not function(event, *params):
                    all_checks_passed = False
                    break
            
            if all_checks_passed:
                logger.info(f"Test {test_index} passed")
                return  # Exit after first successful test
            else:
                logger.info(f"Test {test_index} failed")
        
        # If we get here, all tests failed
        logger.warning("All tests failed for this frame")

    def _handle_idle(self):
        """Handle IDLE state: Create connection and move to WAITING_PREFACE"""
        self.sock = create_socket(self.host, self.port)
        
        if self.test_case.get('tls_enabled', False):
            # Create variables for inputs
            ssl_context = [None]
            
            # Call with variable names
            create_ssl_context(
                inputs=[self.test_case, True],
                outputs=ssl_context
            )
            
            self.sock = ssl_context[0].wrap_socket(
                self.sock,
                server_hostname=self.host
            )
        
        self.sock.connect((self.host, self.port))
        
        config_settings = CONFIG_SETTINGS.copy()
        config_settings.update(self.test_case.get('connection_settings_client', {}))
        config = h2.config.H2Configuration(client_side=True, **config_settings)
        self.conn = h2.connection.H2Connection(config=config)
        
        # Send connection preface
        self.conn.initiate_connection()
        self.sock.sendall(self.conn.data_to_send())
        self._transition_to(ClientState.WAITING_PREFACE)

    def _handle_waiting_preface(self):
        """Wait for server's SETTINGS frame"""
        data = self._receive_frame()
        if data:
            events = self.conn.receive_data(data)
            for event in events:
                log_h2_frame(logger, "RECEIVED", event)
                self._handle_frame(event)

    def _handle_waiting_ack(self):
        """Wait for server's SETTINGS_ACK frame"""
        data = self._receive_frame()
        if data:
            events = self.conn.receive_data(data)
            for event in events:
                log_h2_frame(logger, "RECEIVED", event)
                self._handle_frame(event)

    def _receive_frame(self, timeout: float = FRAME_TIMEOUT_SECONDS) -> bytes:
        """Helper method to receive data with timeout"""
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(SSL_CONFIG.MAX_BUFFER_SIZE)
            return data
        except socket.timeout:
            logger.warning(f"Timeout waiting for frame in state {self.state}")
            return None

    def _handle_receiving_frames(self):
        """Handle response waiting state. Returns number of frames received."""
        expected_server_frames = len(self.test_case.get('server_frames', []))
        self._received_frame_count = 0  # Initialize frame counter
        retry_count = 0
        logger.info(f"expected_server_frames: {expected_server_frames}")
        
        # If we don't expect any frames from server, skip waiting
        if expected_server_frames == 0:
            logger.info("No server frames expected, closing connection")
            self._transition_to(ClientState.CLOSING)
            return 0
        
        while self._received_frame_count < expected_server_frames:
            data = self._receive_frame()
            if data is None:  # Timeout occurred
                retry_count += 1
                if retry_count >= MAX_RETRY_ATTEMPTS:
                    logger.info(f"Max retries ({MAX_RETRY_ATTEMPTS}) reached waiting for server frames, closing connection")
                    self._transition_to(ClientState.CLOSING)
                    return self._received_frame_count
                logger.info(f"Retry {retry_count}/{MAX_RETRY_ATTEMPTS} waiting for server frames")
                continue
            
            else:
                retry_count = 0  # Reset retry counter on successful receive
                logger.info(f"received_server_frames: {self._received_frame_count + 1}")
                events = self.conn.receive_data(data)
                for event in events:
                    log_h2_frame(logger, "RECEIVED", event)
                    self._handle_frame(event)
                
                outbound_data = self.conn.data_to_send()
                if outbound_data:
                    self.sock.sendall(outbound_data)
                    
                self._received_frame_count += 1
        
        # Only transition to CLOSING after receiving all expected frames
        logger.info("All expected frames received, closing connection")
        self._transition_to(ClientState.CLOSING)

    def _handle_sending_frames(self):
        """Send frames based on test case"""
        if self.state != ClientState.SENDING_FRAMES:
            raise RuntimeError(f"Cannot send frames in state {self.state}")
        
        try:
            frames = self.test_case.get('client_frames', [])
            
            for i, frame in enumerate(frames):
                logger.info(f"Sending frame {i+1}/{len(frames)}: {frame.get('type')}")
                send_frame(self.conn, self.sock, frame, self.test_case['id'])

            self._transition_to(ClientState.RECEIVING_FRAMES)

        except Exception as e:
            logger.error(f"Error sending frames: {e}")
            raise

    def _handle_closing(self):
        """Handle CLOSING state: Send GOAWAY if needed and close the connection"""
        try:
            # Only send GOAWAY if it wasn't the last frame sent
            last_frame = self.test_case.get('client_frames', [])[-1] if self.test_case else None
            if not last_frame or last_frame.get('type') != 'GOAWAY':
                logger.info("Sending GOAWAY frame")
                self.conn.close_connection()
                self.sock.sendall(self.conn.data_to_send())
            
            # Wait briefly for any final messages
            try:
                self.sock.settimeout(0.1)
                while not self.conn.state_machine.state == h2.connection.ConnectionState.CLOSED:
                    data = self.sock.recv(SSL_CONFIG.MAX_BUFFER_SIZE)
                    if not data:
                        break
                    events = self.conn.receive_data(data)
                    for event in events:
                        self._handle_frame(event)
            except socket.timeout:
                logger.debug("No more data received during close")
            except Exception as e:
                logger.debug(f"Error during final read: {e}")
        finally:
            self.state = ClientState.CLOSED
            if self.sock:
                self.sock.close()
                self.sock = None
                self.conn = None

    def connect(self):
        """Main connection loop"""
        try:
            while self.state != ClientState.CLOSED:
                handler = self._state_handlers.get(self.state)
                if handler:
                    handler()
                else:
                    raise RuntimeError(f"No handler for state {self.state}")
                
        except Exception as e:
            handle_socket_error(logger, e, "connect")
            self._transition_to(ClientState.CLOSING)  # Instead of calling close()

def main():
    parser = argparse.ArgumentParser(description='HTTP/2 Client')
    parser.add_argument('--test-id', type=int, help='Test case ID to run')
    args = parser.parse_args()

    client = HTTP2Client(test_case=load_test_case(logger, args.test_id))
    
    try:
        client.connect()  # This will handle the entire connection sequence
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        client._handle_closing()

if __name__ == '__main__':
    main()