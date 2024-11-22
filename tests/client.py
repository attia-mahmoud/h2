import overload
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
import time

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
                self.sock = create_ssl_context(self.test_case, is_client=True).wrap_socket(
                    self.sock,
                    server_hostname=self.host
                )
            
            self.sock.connect((self.host, self.port))

            config_settings = CONFIG_SETTINGS.copy()
            config_settings.update(self.test_case.get('connection_settings_client', {}))
            
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
        try:
            for frame in self.test_case.get('client_frames', []):
                send_frame(self.conn, self.sock, frame, self.test_case['id'])
                
                flags = frame.get('flags', {})
                
                # Wait for response unless explicitly told not to
                if not flags.get('END_STREAM') is False:
                    # Try to receive a response with longer timeout
                    self._receive_response(timeout=1.0)
            
            # Add additional wait time for any remaining server frames
            # if self.test_case.get('server_frames'):
            self._receive_response(timeout=1.0)
            
        except Exception as e:
            logger.error(f"Error sending frames: {e}")
            raise
        finally:
            # Always close gracefully
            self.close()

    def _receive_response(self, timeout: float = 0.5) -> str:
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
        """Close the connection gracefully"""
        if self.conn and self.sock:
            try:
                # Only send GOAWAY if connection is still active
                if not self.conn.state_machine.state == h2.connection.ConnectionState.CLOSED:
                    logger.info("Sending GOAWAY frame")
                    self.conn.close_connection()
                    self.sock.sendall(self.conn.data_to_send())
                    
                    # Wait briefly for any final messages
                    try:
                        self.sock.settimeout(0.1)
                        # Only receive data if connection isn't closed
                        while not self.conn.state_machine.state == h2.connection.ConnectionState.CLOSED:
                            data = self.sock.recv(SSL_CONFIG.MAX_BUFFER_SIZE)
                            if not data:
                                break
                            try:
                                events = self.conn.receive_data(data)
                                for event in events:
                                    log_h2_frame(logger, "RECEIVED", event)
                                    if isinstance(event, h2.events.ConnectionTerminated):
                                        logger.info("Received GOAWAY from server")
                                        return
                            except h2.exceptions.ProtocolError as e:
                                logger.debug(f"Protocol error during close: {e}")
                                break
                    except socket.timeout:
                        logger.debug("No more data received during close")
                    except Exception as e:
                        logger.debug(f"Error during final read: {e}")
                    
            except Exception as e:
                logger.debug(f"Error during connection close: {e}")
            finally:
                logger.info("Closing socket connection")
                self.sock.close()
                self.sock = None
                self.conn = None

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