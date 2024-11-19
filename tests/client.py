import h2.connection
import h2.events
import h2.config
import h2.settings
import socket
import json
import sys
import logging
import ssl
import os
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Dict, Optional, Any
import argparse
import hpack

# Create logs directory structure if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'client')
os.makedirs(log_dir, exist_ok=True)

# Configure logging
log_file = os.path.join(log_dir, f'http2_client_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"Starting HTTP/2 client logging to {log_file}")

class FrameType(Enum):
    HEADERS = "HEADERS"
    SETTINGS = "SETTINGS"
    DATA = "DATA"
    WINDOW_UPDATE = "WINDOW_UPDATE"
    RST_STREAM = "RST_STREAM"
    PRIORITY = "PRIORITY"
    CONTINUATION = "CONTINUATION"
    UNKNOWN = "UNKNOWN"

@dataclass
class TestResult:
    test_id: int
    completed: bool
    response: str
    error: Optional[str] = None

class HTTP2Connection:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = None
        self.conn = None
        self.received_packets = []
        self.logger = logging.getLogger(f"{__name__}.HTTP2Connection")
        self.logger.info(f"Initializing HTTP2Connection to {host}:{port}")

    def _log_packet(self, direction: str, frame_type: str, details: Dict[str, Any]) -> None:
        """Log packet details in a prominent way"""
        separator = "=" * 50
        self.logger.info(f"\n{separator}")
        self.logger.info(f"🔵 {direction} {frame_type} FRAME")
        self.logger.info(f"📦 Details: {json.dumps(details, indent=2)}")
        self.logger.info(separator)

    def setup(self, test_case: Dict[str, Any]) -> None:
        """Setup and initialize HTTP/2 connection"""
        self.logger.info("Setting up HTTP/2 connection")
        self._create_socket(test_case)
        self._setup_tls(test_case)
        self._initialize_connection(test_case)
        self.logger.info("Connection setup completed")

    def _create_socket(self, test_case: Dict[str, Any]) -> None:
        self.logger.debug(f"Creating socket connection to {self.host}:{self.port}")
        try:
            self.sock = socket.create_connection((self.host, self.port))
            self.logger.info("Socket connected successfully")
        except Exception as e:
            self.logger.error(f"Failed to create socket connection: {e}", exc_info=True)
            raise

    def _setup_tls(self, test_case: Dict[str, Any]) -> None:
        """Setup TLS if enabled in test case"""
        connection_settings = test_case.get('connection_settings', {})
        if connection_settings.get('tls_enabled', False):
            self.logger.info("Setting up TLS connection")
            try:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                self.sock = context.wrap_socket(self.sock)
                self.logger.info("TLS connection established successfully")
            except Exception as e:
                self.logger.error(f"TLS setup failed: {e}", exc_info=True)
                raise

    def _initialize_connection(self, test_case: Dict[str, Any]) -> None:
        """Initialize HTTP/2 connection"""
        self.logger.info("Initializing HTTP/2 connection")
        connection_settings = test_case.get('connection_settings', {})
        self._apply_connection_settings(connection_settings)
        
        if not connection_settings.get('skip_client_preface', False):
            self._send_client_preface()
        else:
            self.logger.info("Skipping client preface as per test configuration")
            self.conn.initiate_connection()

    def _apply_connection_settings(self, settings: Dict[str, Any]) -> None:
        """Apply connection settings from test case"""
        self.logger.debug(f"Applying connection settings: {settings}")
        config = h2.config.H2Configuration(
            header_encoding='utf-8',
            validate_inbound_headers=False,
            validate_outbound_headers=False,
            normalize_inbound_headers=False,
            normalize_outbound_headers=False,
            skip_settings=settings.get('skip_client_settings', False),
            skip_settings_ack=settings.get('skip_server_settings_ack', False),
            incorrect_connection_preface=settings.get('incorrect_connection_preface', False)
        )
        self.conn = h2.connection.H2Connection(config=config)

    def _send_client_preface(self):
        """Send the client preface"""
        self.logger.debug("Sending client preface")
        self.conn.initiate_connection()

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

    def _send_unknown_frame(self, frame: Dict) -> None:
        """Send an unknown frame type"""
        self.logger.info(f"Preparing UNKNOWN frame: {frame}")
        
        # Create frame header (9 bytes)
        # Length (3 bytes) | Type (1 byte) | Flags (1 byte) | Stream ID (4 bytes)
        payload = frame.get('payload', '').encode('utf-8')
        frame_header = (
            len(payload).to_bytes(3, byteorder='big') +  # Length
            frame['frame_type_id'].to_bytes(1, byteorder='big') +  # Type (99)
            (0).to_bytes(1, byteorder='big') +  # Flags
            frame.get('stream_id', 0).to_bytes(4, byteorder='big')  # Stream ID
        )
        
        # Send frame
        self.logger.info(f"Sending unknown frame type {frame['frame_type_id']}")
        self.sock.sendall(frame_header + payload)

    def send_frames(self, frames: List[Dict]) -> None:
        """Send frames according to test configuration"""
        self.logger.info("\n🔍 Frame Sending Check:")
        self.logger.info(f"Frames to be sent: {[frame['type'] for frame in frames]}")
        self.logger.info(f"Sending {len(frames)} frames")
        for frame in frames:
            frame_type = FrameType(frame['type'].upper())
            self._log_packet("SENDING", frame_type.value, frame)
            
            try:
                if frame_type == FrameType.SETTINGS:
                    self._send_settings_frame(frame)
                elif frame_type == FrameType.PRIORITY:
                    self._send_priority_frame(frame)
                elif frame_type == FrameType.HEADERS:
                    self._send_headers_frame(frame)
                elif frame_type == FrameType.DATA:
                    self._send_data_frame(frame)
                elif frame_type == FrameType.RST_STREAM:
                    self._send_rst_stream_frame(frame)
                elif frame_type == FrameType.WINDOW_UPDATE:
                    self._send_window_update_frame(frame)
                elif frame_type == FrameType.CONTINUATION:
                    self._send_continuation_frame(frame)
                elif frame_type == FrameType.UNKNOWN:
                    self._send_unknown_frame(frame)

                outbound_data = self.conn.data_to_send()
                if outbound_data:
                    self.sock.sendall(outbound_data)
            except Exception as e:
                self.logger.error(f"Error sending {frame_type} frame: {e}", exc_info=True)
                raise

    def _send_settings_frame(self, frame: Dict) -> None:
        """Send a SETTINGS frame"""
        self.logger.debug(f"Preparing SETTINGS frame: {frame}")
        if frame.get('raw_payload', False) or 'stream_id' in frame or 'unknown_setting' in frame:
            # Create a raw SETTINGS frame
            settings_payload = b''
            
            # Handle normal settings
            for setting, value in frame.get('settings', {}).items():
                setting_id = getattr(h2.settings.SettingCodes, setting)
                settings_payload += setting_id.to_bytes(2, byteorder='big')
                settings_payload += value.to_bytes(4, byteorder='big')
            
            # Handle unknown setting if present
            if 'unknown_setting' in frame:
                unknown = frame['unknown_setting']
                settings_payload += unknown['id'].to_bytes(2, byteorder='big')
                settings_payload += unknown['value'].to_bytes(4, byteorder='big')
            
            # Add extra bytes if specified
            if frame.get('extra_bytes', 0) > 0:
                settings_payload += b'\x00' * frame.get('extra_bytes', 0)
            
            # Frame header: length (3 bytes), type (1 byte), flags (1 byte), stream id (4 bytes)
            frame_header = (
                len(settings_payload).to_bytes(3, byteorder='big') +  # Length
                b'\x04' +  # Type (4 for SETTINGS)
                (b'\x01' if 'ACK' in frame.get('flags', []) else b'\x00') +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big') if frame.get('stream_id', False) else b'\x00\x00\x00\x00'
            )
            
            self.sock.sendall(frame_header + settings_payload)
        else:
            # Normal SETTINGS frame
            self.conn.update_settings(frame.get('settings', {}))
            if 'ACK' in frame.get('flags', []):
                self.conn.acknowledge_settings()

    def _send_priority_frame(self, frame: Dict) -> None:
        """Send a PRIORITY frame"""
        stream_id = frame.get('stream_id')
        depends_on = frame.get('depends_on', 0)
        weight = frame.get('weight', 16)
        exclusive = frame.get('exclusive', False)
        
        if 'payload_length' in frame:
            # Create a raw PRIORITY frame with incorrect length
            frame_data = (
                depends_on.to_bytes(4, byteorder='big') +  # 4 bytes for depends_on
                weight.to_bytes(1, byteorder='big') +      # 1 byte for weight
                b'\x00'  # Extra byte to make length incorrect
            )
            
            frame_header = (
                len(frame_data).to_bytes(3, byteorder='big') +  # Length
                b'\x02' +  # Type (2 for PRIORITY)
                b'\x00' +  # Flags
                stream_id.to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.sock.sendall(frame_header + frame_data)
        else:
            self.conn.prioritize(
                stream_id=stream_id,
                depends_on=depends_on,
                weight=weight,
                exclusive=exclusive
            )

    def _send_headers_frame(self, frame: Dict) -> None:
        """Send a HEADERS frame"""
        stream_id = frame.get('stream_id', self.conn.get_next_available_stream_id())

        encoder = hpack.Encoder()
        
        if frame.get('headers'):
            headers = self._format_headers(frame.get('headers'))
        else:
            headers = self._format_custom_headers(frame.get('custom_headers'))

        header_block = encoder.encode(headers)

        if frame.get('reserved_bit', 0):
            stream_id |= 0x80000000  # Set highest bit

        # Create frame header
        frame_header = (
            len(header_block).to_bytes(3, byteorder='big') +  # Length
            b'\x01' +  # Type (1 for HEADERS)
            b'\x04' +  # Flags (END_HEADERS)
            stream_id.to_bytes(4, byteorder='big')  # Reserved bit + Stream ID
        )
    
        # Log and send
        self.logger.info(f"Sending HEADERS frame with reserved bit set")
        self.sock.sendall(frame_header + header_block)

    def _send_data_frame(self, frame: Dict) -> None:
        """Send a DATA frame"""
        stream_id = frame.get('stream_id', 1)
        end_stream = 'END_STREAM' in frame.get('flags', [])
        if 'payload_size' in frame:
            payload_size = frame['payload_size']
            data = b'X' * payload_size
        else:
            data = frame.get('payload', b'')
        
        self.conn.send_data(
            stream_id=stream_id,
            data=data,
            end_stream=end_stream
        )

    def _send_rst_stream_frame(self, frame: Dict) -> None:
        """Send a RST_STREAM frame"""
        stream_id = frame.get('stream_id')
        error_code = frame.get('error_code', 'CANCEL')
        
        if 'payload_length' in frame:
            # Create a raw RST_STREAM frame with incorrect length
            frame_data = (
                getattr(h2.errors.ErrorCodes, error_code).to_bytes(4, byteorder='big') +  # 4 bytes for error code
                b'\x00'  # Extra byte to make length incorrect
            )
            
            frame_header = (
                len(frame_data).to_bytes(3, byteorder='big') +  # Length
                b'\x03' +  # Type (3 for RST_STREAM)
                b'\x00' +  # Flags
                stream_id.to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.sock.sendall(frame_header + frame_data)
        else:
            self.conn.reset_stream(
                stream_id=stream_id, 
                error_code=getattr(h2.errors.ErrorCodes, error_code)
            )

    def _send_window_update_frame(self, frame: Dict) -> None:
        """Send a WINDOW_UPDATE frame"""
        if frame.get('raw_payload', False):
            # Create payload: window size increment
            increment_bytes = frame.get('increment', 0).to_bytes(4, byteorder='big')
            
            # Handle custom length if specified
            if 'force_length' in frame:
                if frame['force_length'] < len(increment_bytes):
                    payload = increment_bytes[:frame['force_length']]
                else:
                    payload = increment_bytes + (b'\x00' * (frame['force_length'] - len(increment_bytes)))
            else:
                payload = increment_bytes
            
            frame_header = (
                len(payload).to_bytes(3, byteorder='big') +  # Length
                b'\x08' +  # Type (8 for WINDOW_UPDATE)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.sock.sendall(frame_header + payload)
        else:
            stream_id = frame.get('stream_id', 0)
            increment = frame.get('increment', 1)
            
            if stream_id == 0:
                self.conn.increment_flow_control_window(increment)
            else:
                self.conn.increment_flow_control_window(increment, stream_id=stream_id)
            self.sock.sendall(self.conn.data_to_send())

    def _send_continuation_frame(self, frame: Dict) -> None:
        """Send a CONTINUATION frame"""
        if frame.get('raw_payload', False):
            # Encode header block
            headers = [(k.encode('utf-8'), v.encode('utf-8')) 
                      for k, v in frame.get('header_block', {}).items()]
            header_block = self.encoder.encode(headers)
            
            frame_header = (
                len(header_block).to_bytes(3, byteorder='big') +  # Length
                b'\x09' +  # Type (9 for CONTINUATION)
                self._encode_flags(frame.get('flags', [])) +  # Flags
                frame.get('stream_id', 0).to_bytes(4, byteorder='big')  # Stream ID
            )
            
            self.sock.sendall(frame_header + header_block)

    def _decode_hex_data(self, hex_data: str) -> Dict[str, Any]:
        """Decode hex data into a human-readable format"""
        try:
            raw_bytes = bytes.fromhex(hex_data)
            
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
                elif frame_type == 0x1:  # HEADERS
                    decoded["payload"] = {
                        "length": len(payload),
                        "hex": payload.hex()
                    }
                elif frame_type == 0x0:  # DATA
                    try:
                        decoded["payload"] = {
                            "text": payload.decode('utf-8', errors='replace'),
                            "hex": payload.hex()
                        }
                    except:
                        decoded["payload"] = {
                            "hex": payload.hex()
                        }
                
                return decoded
            
        except Exception as e:
            return {
                "error": f"Failed to decode hex data: {str(e)}",
                "raw_hex": hex_data
            }

    def receive_response(self) -> str:
        """Handle server response"""
        self.logger.info("Waiting for server response")
        response_data = b''
        
        try:
            while True:
                data = self.sock.recv(65535)
                if not data:
                    self.logger.debug("No more data received")
                    break
                
                # Store the raw received data
                self.received_packets.append({
                    'direction': "RECEIVED",
                    'type': "RAW_DATA",
                    'details': {
                        'length': len(data),
                        'hex_data': data.hex()
                    }
                })
                    
                events = self.conn.receive_data(data)
                
                for event in events:
                    event_dict = {
                        'type': event.__class__.__name__,
                        'stream_id': getattr(event, 'stream_id', None)
                    }
                    
                    if isinstance(event, h2.events.ResponseReceived):
                        event_dict['headers'] = dict(event.headers)
                        self._log_packet("RECEIVED", "HEADERS", event_dict)
                    elif isinstance(event, h2.events.DataReceived):
                        event_dict['data_length'] = len(event.data)
                        event_dict['data'] = event.data.decode('utf-8', errors='replace')
                        self._log_packet("RECEIVED", "DATA", event_dict)
                        response_data += event.data
                        self.conn.acknowledge_received_data(
                            event.flow_controlled_length, 
                            event.stream_id
                        )
                    elif isinstance(event, h2.events.StreamEnded):
                        self._log_packet("RECEIVED", "END_STREAM", event_dict)
                        return response_data.decode('utf-8')
                    else:
                        self._log_packet("RECEIVED", event_dict['type'], event_dict)
                    
                    # Store the parsed H2 event
                    self.received_packets.append({
                        'direction': "RECEIVED",
                        'type': event_dict['type'],
                        'details': event_dict
                    })
                        
                outbound_data = self.conn.data_to_send()
                if outbound_data:
                    self.sock.sendall(outbound_data)
            
            return response_data.decode('utf-8') if response_data else ''
        except Exception as e:
            self.logger.error(f"Error receiving response: {e}", exc_info=True)
            raise

    def close(self) -> None:
        """Close the connection"""
        if self.sock:
            self.logger.info("Closing connection")
            
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
            
            try:
                self.sock.close()
                self.logger.debug("Connection closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing connection: {e}", exc_info=True)

class TestCaseManager:
    def __init__(self, json_path: str):
        self.json_path = json_path
        self.logger = logging.getLogger(f"{__name__}.TestCaseManager")
        self.logger.info(f"Initializing TestCaseManager with JSON path: {json_path}")
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

class HTTP2Client:
    def __init__(self, host: str = 'localhost', port: int = 7700, json_path: str = 'tests/test_cases.json'):
        self.logger = logging.getLogger(f"{__name__}.HTTP2Client")
        self.logger.info(f"Initializing HTTP2Client for {host}:{port}")
        self.connection = HTTP2Connection(host, port)
        self.test_manager = TestCaseManager(json_path)

    def run_test(self, test_id: int) -> TestResult:
        """Run a single test case"""
        self.logger.info(f"Running test case {test_id}")
        error_occurred = False
        response = ""
        error_msg = ""
        
        try:
            test_case, suite = self.test_manager.find_test_case(test_id)
            if not test_case:
                self.logger.error(f"Test {test_id} not found")
                raise ValueError(f"Test {test_id} not found")

            self.logger.info(f"Running test suite: {suite['name']}")
            self.logger.info(f"Section: {suite['section']}")
            self.logger.info(f"Description: {test_case['description']}")

            expected_response = test_case.get('expected_response', {})
            if expected_response.get('type') == 'timeout':
                timeout = expected_response.get('duration', 5)
                self.logger.debug(f"Setting socket timeout to {timeout} seconds")
                self.connection.sock.settimeout(timeout)

            self.connection.setup(test_case)

            
            try:
                response = self._execute_test(test_case)
                self.logger.info("Test execution completed")
            except socket.timeout as e:
                error_occurred = True
                error_msg = f"Unexpected timeout: {str(e)}"
                self.logger.error(error_msg)
            except Exception as e:
                error_occurred = True
                error_msg = str(e)
                self.logger.error(f"Error during test execution: {e}", exc_info=True)
            
        except Exception as e:
            error_occurred = True
            error_msg = str(e)
            self.logger.error(f"Test failed: {e}", exc_info=True)
        finally:
            self.connection.close()
        
        return TestResult(test_id, not error_occurred, response, error_msg if error_occurred else None)

    def _execute_test(self, test_case: Dict[str, Any]) -> str:
        """Execute the test case and return the response"""
        self.logger.debug("Executing test case")
        if 'client_frames' in test_case:
            self.connection.send_frames(test_case['client_frames'])
        
        return self.connection.receive_response()

def main():
    parser = argparse.ArgumentParser(description='Run HTTP/2 client')
    parser.add_argument('test_id', type=int, help='Test ID to run')
    args = parser.parse_args()
    
    logger = logging.getLogger(f"{__name__}.main")
    try:
        logger.info(f"Starting HTTP/2 client with test ID: {args.test_id}")
        client = HTTP2Client()
        result = client.run_test(args.test_id)
        logger.info(f"Test {'COMPLETED' if result.completed else 'FAILED'}")
        if result.error:
            logger.error(f"Test error: {result.error}")
        logger.debug(f"Test response: {result.response}")
        
        print(f"\nTest {'COMPLETED' if result.completed else 'FAILED'}")
        if result.error:
            print(f"Error: {result.error}")
        print(f"Response: {result.response}")
        
        if not result.completed:
            sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()