import h2.connection
import h2.config
import h2.events
import socket
import json
import ssl
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Dict, Optional, Any
import sys
from datetime import datetime
import argparse

# Create logs directory structure if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'server')
os.makedirs(log_dir, exist_ok=True)

# Configure logging
log_file = os.path.join(log_dir, f'http2_server_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"Starting HTTP/2 server logging to {log_file}")

class FrameType(Enum):
    HEADERS = "HEADERS"
    SETTINGS = "SETTINGS"
    DATA = "DATA"
    WINDOW_UPDATE = "WINDOW_UPDATE"
    RST_STREAM = "RST_STREAM"
    PUSH_PROMISE = "PUSH_PROMISE"
    PING = "PING"
    GOAWAY = "GOAWAY"

class TestCaseManager:
    def __init__(self, json_path: str):
        self.json_path = json_path
        self.logger = logging.getLogger(f"{__name__}.TestCaseManager")
        self.logger.debug(f"Initializing TestCaseManager with JSON path: {json_path}")
        self.test_data = self._load_json()

    def _load_json(self) -> Dict:
        """Load and parse JSON test configuration"""
        self.logger.info(f"Loading test configuration from {self.json_path}")
        try:
            with open(self.json_path, 'r') as f:
                data = json.load(f)
                self.logger.debug(f"Successfully loaded {len(data['test_suites'])} test suites")
                return data
        except FileNotFoundError:
            self.logger.error(f"Test configuration file not found: {self.json_path}")
            raise FileNotFoundError(f"{self.json_path} not found")
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON in configuration file: {self.json_path}")
            raise ValueError(f"Invalid JSON in {self.json_path}")

    def find_test_case(self, test_id: int) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Find test case and its parent suite by ID"""
        self.logger.debug(f"Searching for test case with ID: {test_id}")
        for suite in self.test_data['test_suites']:
            for case in suite['cases']:
                if case['id'] == test_id:
                    self.logger.info(f"Found test case {test_id} in suite: {suite['name']}")
                    return case, suite
        self.logger.warning(f"Test case {test_id} not found")
        return None, None

class HTTP2Connection:
    def __init__(self, client_socket: socket.socket, addr: Tuple[str, int], test_case: Dict[str, Any]):
        self.client_socket = client_socket
        self.addr = addr
        self.test_case = test_case
        self.conn = None
        self.received_packets = []
        self.logger = logging.getLogger(f"{__name__}.HTTP2Connection")
        self.logger.info(f"New HTTP2Connection instance created for {addr}")

    def handle(self) -> None:
        """Handle client connection"""
        self.logger.info(f"Starting connection handling for {self.addr}")
        
        try:
            self._initialize_connection()
            self._send_server_frames()
        except Exception as e:
            self.logger.error(f"Error handling client: {e}", exc_info=True)
        finally:
            self.close()

    def _initialize_connection(self) -> None:
        """Initialize H2 connection"""
        self.logger.debug("Initializing H2 connection")
        connection_settings = self.test_case.get('connection_settings', {})
        config = h2.config.H2Configuration(
            client_side=False,
            header_encoding='utf-8',
            validate_inbound_headers=False,
            validate_outbound_headers=False,
            normalize_inbound_headers=False,
            normalize_outbound_headers=False,
            skip_settings=connection_settings.get('skip_server_settings', False),
            skip_settings_ack=connection_settings.get('skip_client_settings_ack', False)
        )
        self.conn = h2.connection.H2Connection(config=config)
        self.logger.debug("H2 connection initialized successfully")

    def _format_headers(self, headers_dict: Dict) -> List[Tuple[str, str]]:
        self.logger.debug(f"Formatting headers: {headers_dict}")
        formatted_headers = []
        
        # Handle pseudo-headers
        if 'pseudo_headers' in headers_dict:
            for name, value in headers_dict['pseudo_headers'].items():
                # Ensure pseudo-header name starts with ':'
                header_name = f":{name}" if not name.startswith(':') else name
                formatted_headers.append((header_name, str(value)))
                self.logger.debug(f"Added pseudo-header: {header_name}: {value}")
        
        # Handle regular headers
        if 'regular_headers' in headers_dict:
            for name, value in headers_dict['regular_headers'].items():
                formatted_headers.append((name.lower(), str(value)))
                self.logger.debug(f"Added regular header: {name}: {value}")
        
        self.logger.debug(f"Final formatted headers: {formatted_headers}")
        return formatted_headers
    
    def _format_custom_headers(self, headers_dict: Dict) -> List[Tuple[str, str]]:
        """Format custom headers from test case"""
        self.logger.debug(f"Formatting custom headers: {headers_dict}")
        return [(name.lower(), str(value)) for name, value in headers_dict.items()]

    def _send_server_frames(self) -> None:
        """Send frames specified in test case"""
        self.logger.info("Starting to send server frames")
        try:
            for frame in self.test_case.get('server_frames', []):
                frame_type = FrameType(frame['type'].upper())
                self.logger.debug(f"Processing frame of type: {frame_type}")
                
                if frame_type == FrameType.SETTINGS:
                    self._send_settings_frame(frame)
                elif frame_type == FrameType.HEADERS:
                    self._send_headers_frame(frame)
                elif frame_type == FrameType.DATA:
                    self._send_data_frame(frame)
                elif frame_type == FrameType.PUSH_PROMISE:
                    self._send_push_promise_frame(frame)
                elif frame_type == FrameType.RST_STREAM:
                    self._send_rst_stream_frame(frame)
                elif frame_type == FrameType.GOAWAY:
                    self._send_goaway_frame(frame)
                elif frame_type == FrameType.PING:
                    self._send_ping_frame(frame)
                
                # Send any pending data after each frame
                outbound_data = self.conn.data_to_send()
                if outbound_data:
                    self.client_socket.sendall(outbound_data)
                
            # Wait for and process client frames before closing
            self._process_client_frames()
        except Exception as e:
            self.logger.error(f"Error sending server frames: {e}", exc_info=True)
            raise

    def _process_client_frames(self) -> None:
        """Process incoming client frames"""
        self.logger.info("Processing client frames")
        self.client_socket.settimeout(5.0)  # 5 second timeout
        
        MAX_FRAME_SIZE = 65535  # Standard HTTP/2 max frame size
        
        try:
            while True:
                data = self.client_socket.recv(MAX_FRAME_SIZE)
                if not data:
                    self.logger.info("Client closed connection")
                    break
                
                if len(data) >= MAX_FRAME_SIZE:
                    error_msg = f"Received frame size ({len(data)}) exceeds maximum allowed size ({MAX_FRAME_SIZE})"
                    self.logger.error(error_msg)
                    return
                
                # Store the raw received data
                self.received_packets.append({
                    'direction': "RECEIVED",
                    'type': "RAW_DATA",
                    'details': {
                        'length': len(data),
                        'hex_data': data.hex()
                    }
                })
                
                self.logger.info(f"Received {len(data)} bytes from client")
                events = self.conn.receive_data(data)
                
                # Process H2 events if any were generated
                for event in events:
                    event_dict = {
                        'type': event.__class__.__name__,
                        'stream_id': getattr(event, 'stream_id', None),
                    }
                    
                    if hasattr(event, 'headers'):
                        event_dict['headers'] = dict(event.headers)
                    if hasattr(event, 'data'):
                        event_dict['data_length'] = len(event.data)
                    if hasattr(event, 'error_code'):
                        event_dict['error_code'] = event.error_code
                    
                    self._log_packet("RECEIVED", event_dict['type'], event_dict)
                    # Store the parsed H2 event
                    self.received_packets.append({
                        'direction': "RECEIVED",
                        'type': event_dict['type'],
                        'details': event_dict
                    })
                
                outbound_data = self.conn.data_to_send()
                if outbound_data:
                    self.client_socket.sendall(outbound_data)
        except Exception as e:
            self.logger.error(f"Error processing client frames: {e}", exc_info=True)
            raise

    def _log_packet(self, direction: str, frame_type: str, details: Dict[str, Any]) -> None:
        """Log packet details in a prominent way"""
        separator = "=" * 50
        self.logger.info(f"\n{separator}")
        self.logger.info(f"🔵 {direction} {frame_type} FRAME")
        self.logger.info(f"📦 Details: {json.dumps(details, indent=2)}")
        self.logger.info(separator)

    def _send_settings_frame(self, frame: Dict) -> None:
        """Send a SETTINGS frame"""
        self._log_packet("SENDING", "SETTINGS", frame)
        self.logger.debug(f"Preparing to send SETTINGS frame: {frame}")
        if frame.get('raw_payload', False) or 'stream_id' in frame:
            self.logger.info("Sending raw SETTINGS frame")
            settings_payload = b''
            for setting, value in frame.get('settings', {}).items():
                self.logger.debug(f"Adding setting {setting}={value}")
                setting_id = getattr(h2.settings.SettingCodes, setting)
                settings_payload += setting_id.to_bytes(2, byteorder='big')
                settings_payload += value.to_bytes(4, byteorder='big')
            
            frame_header = (
                len(settings_payload).to_bytes(3, byteorder='big') +
                b'\x04' +
                (b'\x01' if 'ACK' in frame.get('flags', []) else b'\x00') +
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')
            )
            
            self.client_socket.sendall(frame_header + settings_payload)
            self.logger.debug("Raw SETTINGS frame sent successfully")
        else:
            self.logger.info("Sending SETTINGS frame using h2 library")
            self.conn.update_settings(frame.get('settings', {}))
            if 'ACK' in frame.get('flags', []):
                self.conn.acknowledge_settings()
            self.client_socket.sendall(self.conn.data_to_send())
            self.logger.debug("SETTINGS frame sent successfully via h2 library")

    def _send_headers_frame(self, frame: Dict) -> None:
        """Send a HEADERS frame"""
        self._log_packet("SENDING", "HEADERS", frame)
        if frame.get('raw_payload', False):
            headers = self._format_headers(frame.get('headers', {}))
            header_block = self.conn.encoder.encode(headers)
            
            frame_header = (
                len(header_block).to_bytes(3, byteorder='big') +  # Length
                b'\x01' +  # Type (1 for HEADERS)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 1).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + header_block)
        else:
            stream_id = frame.get('stream_id', 1)
            headers = self._format_headers(frame.get('headers', {}))
            end_stream = 'END_STREAM' in frame.get('flags', [])
            
            self.conn.send_headers(
                stream_id=stream_id,
                headers=headers,
                end_stream=end_stream
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_data_frame(self, frame: Dict) -> None:
        """Send a DATA frame"""
        self._log_packet("SENDING", "DATA", frame)
        if frame.get('raw_payload', False):
            data = frame.get('data', '').encode('utf-8')
            
            frame_header = (
                len(data).to_bytes(3, byteorder='big') +  # Length
                b'\x00' +  # Type (0 for DATA)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 1).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + data)
        else:
            stream_id = frame.get('stream_id', 1)
            data = frame.get('data', '').encode('utf-8')
            end_stream = 'END_STREAM' in frame.get('flags', [])
            
            self.conn.send_data(
                stream_id=stream_id,
                data=data,
                end_stream=end_stream
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_push_promise_frame(self, frame: Dict) -> None:
        """Send a PUSH_PROMISE frame"""
        self._log_packet("SENDING", "PUSH_PROMISE", frame)
        if frame.get('raw_payload', False) or frame.get('stream_id', 0) == 0:
            headers = self._format_headers(frame.get('headers', {}))
            header_block = self.conn.encoder.encode(headers)
            
            # Create the frame payload
            frame_payload = frame.get('promised_stream_id', 2).to_bytes(4, byteorder='big')
            
            # Add padding length byte if PADDED flag is set
            if 'PADDED' in frame.get('flags', []):
                padding_length = frame.get('padding_length', 0)
                frame_payload = bytes([padding_length]) + frame_payload
            
            # Add header block
            frame_payload += header_block
            
            # Add padding if PADDED flag is set
            if 'PADDED' in frame.get('flags', []):
                frame_payload += b'\x00' * frame.get('padding_length', 0)
            
            frame_header = (
                len(frame_payload).to_bytes(3, byteorder='big') +  # Length
                b'\x05' +  # Type (5 for PUSH_PROMISE)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + frame_payload)
        else:
            stream_id = frame.get('stream_id', 1)
            promised_stream_id = frame.get('promised_stream_id', 2)
            headers = self._format_headers(frame.get('headers', {}))
            
            self.conn.push_stream(
                stream_id=stream_id,
                promised_stream_id=promised_stream_id,
                request_headers=headers
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_rst_stream_frame(self, frame: Dict) -> None:
        """Send a RST_STREAM frame"""
        self._log_packet("SENDING", "RST_STREAM", frame)
        if frame.get('raw_payload', False):
            error_code = getattr(h2.errors.ErrorCodes, frame.get('error_code', 'PROTOCOL_ERROR'))
            payload = error_code.to_bytes(4, byteorder='big')
            
            frame_header = (
                len(payload).to_bytes(3, byteorder='big') +  # Length
                b'\x03' +  # Type (3 for RST_STREAM)
                b'\x00' +  # Flags (no flags for RST_STREAM)
                frame.get('stream_id', 1).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + payload)
        else:
            stream_id = frame.get('stream_id', 1)
            error_code = frame.get('error_code', 'PROTOCOL_ERROR')
            
            self.conn.reset_stream(
                stream_id=stream_id,
                error_code=getattr(h2.errors.ErrorCodes, error_code)
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_goaway_frame(self, frame: Dict) -> None:
        """Send a GOAWAY frame"""
        self._log_packet("SENDING", "GOAWAY", frame)
        if frame.get('raw_payload', False) or 'stream_id' in frame:
            # Convert error code to int if string provided
            if isinstance(frame.get('error_code'), str):
                error_code = getattr(h2.errors.ErrorCodes, frame['error_code'])
            else:
                error_code = frame.get('error_code', h2.errors.ErrorCodes.NO_ERROR)
            
            # Create payload: last_stream_id (4 bytes) + error_code (4 bytes)
            payload = (
                frame.get('last_stream_id', 0).to_bytes(4, byteorder='big') +
                error_code.to_bytes(4, byteorder='big')
            )
            
            # Add debug data if provided
            if 'debug_data' in frame:
                if isinstance(frame['debug_data'], str):
                    payload += frame['debug_data'].encode('utf-8')
                else:
                    payload += frame['debug_data']
            
            frame_header = (
                len(payload).to_bytes(3, byteorder='big') +  # Length
                b'\x07' +  # Type (7 for GOAWAY)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')  # Stream ID (normally 0)
            )
            
            self.client_socket.sendall(frame_header + payload)
        else:
            # Use h2 library's GOAWAY support
            error_code = frame.get('error_code', 'NO_ERROR')
            if isinstance(error_code, str):
                error_code = getattr(h2.errors.ErrorCodes, error_code)
                
            last_stream_id = frame.get('last_stream_id', 0)
            debug_data = frame.get('debug_data', b'').encode('utf-8') if isinstance(frame.get('debug_data'), str) else frame.get('debug_data', b'')
            
            self.conn.close_connection(
                error_code=error_code,
                last_stream_id=last_stream_id,
                additional_data=debug_data
            )
            self.client_socket.sendall(self.conn.data_to_send())

    def _send_ping_frame(self, frame: Dict) -> None:
        """Send a PING frame"""
        self._log_packet("SENDING", "PING", frame)
        if frame.get('raw_payload', False) or 'stream_id' in frame:
            # Convert string payload to bytes if needed
            if isinstance(frame.get('payload'), str):
                payload = frame['payload'].encode('utf-8')
            else:
                payload = frame.get('payload', b'\x00' * 8)
            
            # Handle custom length if specified, otherwise ensure 8 bytes
            if 'force_length' in frame:
                if len(payload) > frame['force_length']:
                    payload = payload[:frame['force_length']]
                elif len(payload) < frame['force_length']:
                    payload = payload.ljust(frame['force_length'], b'\x00')
            else:
                # Default behavior: ensure exactly 8 bytes
                if len(payload) < 8:
                    payload = payload.ljust(8, b'\x00')
                elif len(payload) > 8:
                    payload = payload[:8]
            
            frame_header = (
                len(payload).to_bytes(3, byteorder='big') +  # Length (from payload)
                b'\x06' +  # Type (6 for PING)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.client_socket.sendall(frame_header + payload)
        else:
            # Use h2 library's PING support
            opaque_data = frame.get('payload', b'\x00' * 8)
            if isinstance(opaque_data, str):
                opaque_data = opaque_data.encode('utf-8')
            
            self.conn.ping(opaque_data)
            self.client_socket.sendall(self.conn.data_to_send())

    def _encode_flags(self, flags: List[str]) -> bytes:
        """Helper method to encode frame flags"""
        flag_byte = 0
        flag_mapping = {
            'END_STREAM': 0x1,
            'END_HEADERS': 0x4,
            'PADDED': 0x8,
            'PRIORITY': 0x20,
            'ACK': 0x1
        }
        for flag in flags:
            if flag in flag_mapping:
                flag_byte |= flag_mapping[flag]
        return bytes([flag_byte])

    def _decode_hex_data(self, hex_data: str) -> Dict[str, Any]:
        """Decode hex data into a human-readable format"""
        try:
            raw_bytes = bytes.fromhex(hex_data)
            
            # Try to decode as HTTP/2 preface
            if raw_bytes.startswith(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'):
                return {
                    "type": "HTTP/2 Preface",
                    "value": "PRI * HTTP/2.0\\r\\n\\r\\nSM\\r\\n\\r\\n",
                    "remaining_hex": raw_bytes[24:].hex()  # Skip preface bytes
                }
            
            # Try to decode as HTTP/2 frame
            if len(raw_bytes) >= 9:  # Minimum frame size is 9 bytes
                length = int.from_bytes(raw_bytes[0:3], byteorder='big')
                frame_type = raw_bytes[3]
                flags = raw_bytes[4]
                stream_id = int.from_bytes(raw_bytes[5:9], byteorder='big') & 0x7FFFFFFF
                payload = raw_bytes[9:9+length] if len(raw_bytes) >= 9+length else raw_bytes[9:]
                
                frame_types = {
                    0x0: "DATA",
                    0x1: "HEADERS",
                    0x2: "PRIORITY",
                    0x3: "RST_STREAM",
                    0x4: "SETTINGS",
                    0x5: "PUSH_PROMISE",
                    0x6: "PING",
                    0x7: "GOAWAY",
                    0x8: "WINDOW_UPDATE",
                    0x9: "CONTINUATION"
                }
                
                flag_meanings = {
                    0x1: "END_STREAM",
                    0x4: "END_HEADERS",
                    0x8: "PADDED",
                    0x20: "PRIORITY"
                }
                
                active_flags = [flag_meanings[f] for f in flag_meanings if flags & f]
                
                decoded = {
                    "frame": {
                        "length": length,
                        "type": frame_types.get(frame_type, f"Unknown(0x{frame_type:02x})"),
                        "flags": active_flags,
                        "stream_id": stream_id,
                    }
                }
                
                # Decode payload based on frame type
                if frame_type == 0x4:  # SETTINGS
                    settings = []
                    for i in range(0, len(payload), 6):
                        if i + 6 <= len(payload):
                            identifier = int.from_bytes(payload[i:i+2], byteorder='big')
                            value = int.from_bytes(payload[i+2:i+6], byteorder='big')
                            settings.append({
                                "identifier": identifier,
                                "value": value
                            })
                    decoded["settings"] = settings
                
                return decoded
                
        except Exception as e:
            return {
                "error": f"Failed to decode hex data: {str(e)}",
                "raw_hex": hex_data
            }

    def close(self) -> None:
        """Close the connection"""
        self.logger.info(f"Closing connection to {self.addr}")
        
        # Print summary of all received packets
        if self.received_packets:
            separator = "=" * 80
            self.logger.info(f"\n{separator}")
            self.logger.info("📋 CONNECTION SUMMARY - ALL RECEIVED PACKETS")
            self.logger.info(separator)
            
            for idx, packet in enumerate(self.received_packets, 1):
                self.logger.info(f"\n🔷 Packet #{idx}")
                self.logger.info(f"Type: {packet['type']}")
                
                # Add decoded information for RAW_DATA packets
                if packet['type'] == "RAW_DATA" and 'hex_data' in packet['details']:
                    decoded_data = self._decode_hex_data(packet['details']['hex_data'])
                    packet['details']['decoded'] = decoded_data
                
                self.logger.info(f"Details: {json.dumps(packet['details'], indent=2)}")
            
            self.logger.info(f"\n{separator}")
            self.logger.info(f"Total packets received: {len(self.received_packets)}")
            self.logger.info(separator)
        else:
            self.logger.info("No packets were received during this connection")

        self.client_socket.close()
        self.logger.debug("Connection closed successfully")

class HTTP2Server:
    def __init__(self, host: str = 'localhost', port: int = 7700, json_path: str = 'tests/test_cases.json'):
        self.host = host
        self.port = port
        self.sock = None
        self.logger = logging.getLogger(f"{__name__}.HTTP2Server")
        self.logger.info(f"Initializing HTTP2Server on {host}:{port}")
        self.test_manager = TestCaseManager(json_path)

    def _setup_socket(self, test_id: int) -> None:
        """Setup server socket with test case configuration"""
        self.logger.info(f"Setting up server socket for test ID: {test_id}")
        test_case, suite = self.test_manager.find_test_case(test_id)
        if not test_case:
            self.logger.error(f"Test {test_id} not found")
            raise ValueError(f"Test {test_id} not found")

        self.logger.info(f"Running test suite: {suite['name']}")
        self.logger.info(f"Section: {suite['section']}")
        self.logger.info(f"Description: {test_case['description']}")

        self._create_socket()
        self._configure_tls(test_case)
        self._bind_and_listen()

    def _create_socket(self) -> None:
        """Create and configure base socket"""
        self.logger.debug("Creating server socket")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.logger.debug("Server socket created successfully")

    def _configure_tls(self, test_case: Dict[str, Any]) -> None:
        """Configure TLS if specified in test case"""
        connection_settings = test_case.get('connection_settings', {})
        if connection_settings.get('tls_enabled', False):
            self.logger.info("Setting up TLS...")
            try:
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                context.load_cert_chain(certfile="tests/certs/server.crt", keyfile="tests/certs/server.key")
                self.sock = context.wrap_socket(self.sock, server_side=True)
                self.logger.info("TLS configured successfully")
            except Exception as e:
                self.logger.error(f"Failed to configure TLS: {e}", exc_info=True)
                raise

    def _bind_and_listen(self) -> None:
        """Bind socket and start listening"""
        try:
            self.sock.bind((self.host, self.port))
            self.sock.listen(5)
            self.sock.settimeout(10)
            self.logger.info(f"Server bound to {self.host}:{self.port} and listening")
        except Exception as e:
            self.logger.error(f"Failed to bind and listen: {e}", exc_info=True)
            raise

    def run(self, test_id: int) -> None:
        """Run the server for a specific test case"""
        self.logger.info(f"Starting server for test ID: {test_id}")
        test_case, suite = self.test_manager.find_test_case(test_id)
        if not test_case:
            self.logger.error(f"Test {test_id} not found")
            raise ValueError(f"Test {test_id} not found")

        self._setup_socket(test_id)
        self.logger.info(f"Server listening on {self.host}:{self.port}")
        
        try:
            while True:
                self.logger.debug("Waiting for client connection...")
                client_socket, addr = self.sock.accept()
                self.logger.info(f"Accepted connection from {addr}")
                connection = HTTP2Connection(client_socket, addr, test_case)
                connection.handle()
                break
        except socket.timeout:
            self.logger.warning("Connection timeout while waiting for client")
        except KeyboardInterrupt:
            self.logger.info("Server shutdown requested via keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Unexpected error during server operation: {e}", exc_info=True)
        finally:
            if self.sock:
                self.logger.info("Closing server socket")
                self.sock.close()

def main():
    parser = argparse.ArgumentParser(description='Run HTTP/2 server')
    parser.add_argument('test_id', type=int, help='Test ID to run')
    args = parser.parse_args()
    
    logger = logging.getLogger(f"{__name__}.main")
    try:
        logger.info(f"Starting HTTP/2 server with test ID: {args.test_id}")
        server = HTTP2Server()
        server.run(args.test_id)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()