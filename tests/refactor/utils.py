import ssl
import logging
import socket
from typing import Dict, Any, Optional, Tuple, List
import h2
import json
import h2.events
import os
from datetime import datetime
import argparse
import h2.connection

# Configure shared logging
def setup_logging(name: str) -> logging.Logger:
    """Setup logging configuration"""
    # Set hpack and h2 loggers to INFO level to suppress debug messages
    logging.getLogger('hpack').setLevel(logging.INFO)
    logging.getLogger('h2').setLevel(logging.INFO)
    
    # Create logs directory structure
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    client_log_dir = os.path.join(log_dir, 'client')
    server_log_dir = os.path.join(log_dir, 'server')
    
    # Create directories if they don't exist
    os.makedirs(client_log_dir, exist_ok=True)
    os.makedirs(server_log_dir, exist_ok=True)
    
    # Determine if this is client or server based on the name
    is_client = 'client' in name.lower()
    log_subdir = 'client' if is_client else 'server'
    
    # Create log file path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, log_subdir, f'http2_{log_subdir}_{timestamp}.log')
    
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')
    
    # Create and configure file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Create and configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler, console_handler]
    )
    
    logger = logging.getLogger(name)
    logger.info(f"Logging initialized. Log file: {log_file}")
    
    return logger

class SSL_CONFIG:
    """SSL configuration constants"""
    CERT_PATH = "tests/certs/server.crt"
    KEY_PATH = "tests/certs/server.key"
    ALPN_PROTOCOLS = ['h2']
    MAX_BUFFER_SIZE = 65535

def create_ssl_context(is_client: bool = True) -> ssl.SSLContext:
    """Create SSL context for client or server"""
    if is_client:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(
            certfile=SSL_CONFIG.CERT_PATH,
            keyfile=SSL_CONFIG.KEY_PATH
        )
    
    context.set_alpn_protocols(SSL_CONFIG.ALPN_PROTOCOLS)
    return context

def create_socket(host: str, port: int, is_server: bool = False) -> socket.socket:
    """Create and configure a socket"""
    sock = socket.socket()
    if is_server:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
    return sock

def handle_socket_error(logger: logging.Logger, error: Exception, context: str):
    """Handle socket-related errors"""
    logger.error(f"Socket error in {context}: {error}", exc_info=True)
    raise

def log_h2_frame(logger: logging.Logger, direction: str, event: Any) -> None:
    """Log HTTP/2 frame details"""
    event_type = event.__class__.__name__
    
    separator = "=" * 50
    logger.info(f"\n{separator}")
    logger.info(f"🔵 {direction} {event_type} FRAME")
    
    # Log basic frame info
    logger.info(f"Stream ID: {getattr(event, 'stream_id', 'N/A')}")
    
    # Add specific details based on frame type
    if isinstance(event, h2.events.RequestReceived):
        headers = dict(event.headers)
        logger.info("Headers:")
        for k, v in headers.items():
            logger.info(f"  {k}: {v}")
            
    elif isinstance(event, h2.events.ResponseReceived):
        headers = dict(event.headers)
        logger.info("Headers:")
        for k, v in headers.items():
            logger.info(f"  {k}: {v}")
            
    elif isinstance(event, h2.events.SettingsAcknowledged):
        logger.info("Settings: ACK received")
        
    elif isinstance(event, h2.events.RemoteSettingsChanged):
        logger.info("Changed Settings:")
        for setting, value in event.changed_settings.items():
            logger.info(f"  {setting.name}: {value}")
            
    elif isinstance(event, h2.events.WindowUpdated):
        logger.info(f"Window Update Delta: {event.delta}")
        
    elif isinstance(event, h2.events.DataReceived):
        logger.info(f"Data Length: {len(event.data)}")
        logger.info(f"Flow Controlled Length: {event.flow_controlled_length}")
        
    elif isinstance(event, h2.events.PriorityUpdated):
        logger.info(f"Depends On: {event.depends_on}")
        logger.info(f"Weight: {event.weight}")
        logger.info(f"Exclusive: {event.exclusive}")
        
    logger.info(separator)

def load_test_case(logger: logging.Logger, test_id: int) -> Optional[Dict]:
    """Load a specific test case by ID from the test cases file"""
    try:
        with open('tests/test_cases.json', 'r') as f:
            test_data = json.load(f)
            
        # Search through all test suites for the specified test ID
        for test_suite in test_data['test_suites']:
            for test_case in test_suite['cases']:
                if test_case['id'] == test_id:
                    logger.info(f"\nLoaded test case {test_id}:")
                    logger.info(f"Suite: {test_suite['name']}")
                    logger.info(f"Section: {test_suite['section']}")
                    logger.info(f"Description: {test_case['description']}\n")
                    return test_case
                    
        logger.error(f"Test case with ID {test_id} not found")
        return None
        
    except FileNotFoundError:
        logger.error("test_cases.json file not found")
        return None
    except json.JSONDecodeError:
        logger.error("Error parsing test_cases.json")
        return None
    
# Default H2Configuration settings
CONFIG_SETTINGS = {
    'header_encoding': 'utf-8',
    'validate_inbound_headers': False,
    'validate_outbound_headers': False,
    'normalize_inbound_headers': False,
    'normalize_outbound_headers': False,
}

def format_headers(headers_dict: Dict) -> List[Tuple[str, str]]:
    """Convert headers dictionary to h2 compatible format
    Args:
        headers_dict: Dictionary containing pseudo_headers and regular_headers
    Returns:
        List of (name, value) tuples in correct order
    """
    headers = []
    
    for name, value in headers_dict.items():
        headers.append((name, str(value)))
        
    return headers

def send_frame(conn: h2.connection.H2Connection, sock: socket.socket, 
               frame_data: Dict, logger: logging.Logger) -> None:
    """Send a single H2 frame
    Args:
        conn: H2Connection instance
        sock: Socket to send data on
        frame_data: Frame configuration from test case
        logger: Logger instance
    """
    frame_type = frame_data.get('type')
    
    logger.info(f"Sending {frame_type} frame on stream {frame_data.get('stream_id')}")
    
    if frame_type == 'HEADERS':
        send_headers_frame(conn, frame_data)
    
    # Send any pending data
    outbound_data = conn.data_to_send()
    if outbound_data:
        sock.sendall(outbound_data)

def send_headers_frame(conn: h2.connection.H2Connection, frame_data: Dict) -> None:
    """Send a HEADERS frame"""
    stream_id = frame_data.get('stream_id')
    headers = format_headers(frame_data.get('headers', {}))
    end_stream = 'END_STREAM' in frame_data.get('flags', [])
    end_headers = 'END_HEADERS' in frame_data.get('flags', [])
    
    conn.send_headers(
        stream_id=stream_id,
        headers=headers,
        end_stream=end_stream,
        end_headers=end_headers
    )
