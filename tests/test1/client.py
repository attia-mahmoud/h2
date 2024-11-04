import h2.connection
import socket
import time

# Establish a TCP connection
sock = socket.create_connection(('localhost', 7701), timeout=10)
conn = h2.connection.H2Connection()

# Initialize the HTTP/2 connection
conn.initiate_connection()
sock.sendall(conn.data_to_send())

# Create headers
headers = [
    (':method', 'GET'),
    (':authority', 'localhost'),
    (':scheme', 'http'),
    (':path', '/'),
    ('connection', 'keep-alive')  # Non-conformant header
]

# Send headers frame
stream_id = conn.get_next_available_stream_id()
conn.send_headers(stream_id, headers, end_stream=True)
sock.sendall(conn.data_to_send())

# Wait for response
try:
    while True:
        data = sock.recv(65535)
        if not data:
            break
            
        events = conn.receive_data(data)
        for event in events:
            print(f"Received event: {event}")
            
        if conn.data_to_send():
            sock.sendall(conn.data_to_send())
            
except Exception as e:
    print(f"Error: {e}")
finally:
    # Clean shutdown
    conn.close_connection()
    sock.sendall(conn.data_to_send())
    sock.close()