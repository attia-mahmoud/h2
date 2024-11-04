import h2.connection
import socket

# Establish a TCP connection
sock = socket.create_connection(('localhost', 8080), timeout=10)
conn = h2.connection.H2Connection()

# Initialize the HTTP/2 connection
conn.initiate_connection()
sock.sendall(conn.data_to_send())

# Wait for the initial flow control window update from the server
sock.recv(65535)

# Create headers for a simple GET request
headers = [
    (':method', 'GET'),
    (':authority', 'localhost'),
    (':scheme', 'http'),
    (':path', '/')
]
conn.send_headers(1, headers)
sock.sendall(conn.data_to_send())

# Now send a non-conformant DATA frame that exceeds flow-control limits
data = b"x" * 70000  # Exceeds default flow-control window (65,535 bytes)
conn.send_data(1, data)
sock.sendall(conn.data_to_send())

# Close the connection
conn.close_connection()
sock.sendall(conn.data_to_send())
sock.close()