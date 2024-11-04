import h2.connection
import socket

# Establish a TCP connection
sock = socket.create_connection(('localhost', 8080), timeout=10)
conn = h2.connection.H2Connection()

# Initialize the HTTP/2 connection
conn.initiate_connection()
sock.sendall(conn.data_to_send())

# Send a SETTINGS frame to establish header table size (server should respond with its settings)
sock.recv(65535)  # Receiving the initial server response

# Now send headers with an invalid dynamic table size update
# For example, the server's SETTINGS_HEADER_TABLE_SIZE might be set to 4096 bytes, but we'll exceed that
headers = [
    (':method', 'GET'),
    (':authority', 'localhost'),
    (':scheme', 'http'),
    (':path', '/')
]
conn.send_headers(1, headers)
conn.increment_flow_control_window(65536, stream_id=1)  # Invalid large header table size
sock.sendall(conn.data_to_send())

# Close the connection
conn.close_connection()
sock.sendall(conn.data_to_send())
sock.close()