import h2.connection
import socket

# Establish a TCP connection
sock = socket.create_connection(('localhost', 8080), timeout=10)
conn = h2.connection.H2Connection()

# Initialize the HTTP/2 connection
conn.initiate_connection()
sock.sendall(conn.data_to_send())

# Send a simple GET request
headers = [
    (':method', 'GET'),
    (':authority', 'localhost'),
    (':scheme', 'http'),
    (':path', '/')
]
conn.send_headers(1, headers)
sock.sendall(conn.data_to_send())

# Now the server starts sending data...
# Let's say we receive some data (but don't acknowledge it yet):
data = sock.recv(65535)

# Instead of sending a proper WINDOW_UPDATE, let's reduce the window below the outstanding data
# The outstanding data might be 50,000 bytes, so we reduce it to less than that
conn.increment_flow_control_window(-40000, stream_id=1)  # Invalid flow control window reduction
sock.sendall(conn.data_to_send())

# Close the connection
conn.close_connection()
sock.sendall(conn.data_to_send())
sock.close()