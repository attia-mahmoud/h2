import h2.connection
import socket

# Establish a TCP connection
sock = socket.create_connection(('localhost', 8080), timeout=10)
conn = h2.connection.H2Connection()

# Initialize the HTTP/2 connection
conn.initiate_connection()
sock.sendall(conn.data_to_send())

# Send the first request with stream ID 1
headers1 = [
    (':method', 'GET'),
    (':authority', 'localhost'),
    (':scheme', 'http'),
    (':path', '/')
]
conn.send_headers(1, headers1)  # Stream ID 1
sock.sendall(conn.data_to_send())

# Now attempt to reuse the same stream ID (1) for a new request, which is non-conformant
headers2 = [
    (':method', 'POST'),
    (':authority', 'localhost'),
    (':scheme', 'http'),
    (':path', '/new')
]
conn.send_headers(1, headers2)  # Reusing Stream ID 1 (invalid)
sock.sendall(conn.data_to_send())

# Close the connection
conn.close_connection()
sock.sendall(conn.data_to_send())
sock.close()