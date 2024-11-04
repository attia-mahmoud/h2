import h2.connection
import socket

# Establish a TCP connection
sock = socket.create_connection(('localhost', 8080), timeout=10)
conn = h2.connection.H2Connection()

# Initialize the HTTP/2 connection
conn.initiate_connection()
sock.sendall(conn.data_to_send())

# Send the initial headers to open a stream
headers = [
    (':method', 'GET'),
    (':authority', 'localhost'),
    (':scheme', 'http'),
    (':path', '/')
]
conn.send_headers(1, headers)
sock.sendall(conn.data_to_send())

# Send a DATA frame that exceeds the default SETTINGS_MAX_FRAME_SIZE (16,384 bytes)
# For example, send a 20,000-byte DATA frame, which is too large
oversized_data = b'a' * 20000  # 20,000 bytes of data
conn.send_data(1, oversized_data)
sock.sendall(conn.data_to_send())

# Close the connection
conn.close_connection()
sock.sendall(conn.data_to_send())
sock.close()