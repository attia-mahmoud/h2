import h2.connection
import socket

# Establish a TCP connection
sock = socket.create_connection(('localhost', 8080), timeout=10)
conn = h2.connection.H2Connection()

# Initialize the HTTP/2 connection
conn.initiate_connection()
sock.sendall(conn.data_to_send())

# Send headers with a regular header before a pseudo-header (non-conformant)
headers = [
    ('content-type', 'application/json'),  # Regular header first (invalid)
    (':method', 'GET'),                    # Pseudo-header after regular header
    (':path', '/'),
    (':scheme', 'http'),
    (':authority', 'localhost')
]
conn.send_headers(1, headers)
sock.sendall(conn.data_to_send())

# Close the connection
conn.close_connection()
sock.sendall(conn.data_to_send())
sock.close()