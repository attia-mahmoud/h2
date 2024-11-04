import h2.connection
import socket

# Establish a TCP connection
sock = socket.create_connection(('localhost', 8080), timeout=10)
conn = h2.connection.H2Connection()

# Initialize the HTTP/2 connection
conn.initiate_connection()
sock.sendall(conn.data_to_send())

# Send a simple GET request with the END_STREAM flag set (closing the stream)
headers = [
    (':method', 'GET'),
    (':authority', 'localhost'),
    (':scheme', 'http'),
    (':path', '/')
]
conn.send_headers(1, headers, end_stream=True)
sock.sendall(conn.data_to_send())

# Now try to send a DATA frame on the closed stream (non-conformant)
data = b"This data should not be allowed because the stream is closed."
conn.send_data(1, data)  # Stream 1 is already closed
sock.sendall(conn.data_to_send())

# Close the connection
conn.close_connection()
sock.sendall(conn.data_to_send())
sock.close()