import h2.connection
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('localhost', 8080))
sock.listen(5)

conn, addr = sock.accept()
h2_conn = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=False))
h2_conn.initiate_connection()

# Receive and process data
data = conn.recv(65535)
events = h2_conn.receive_data(data)

# Check for PROTOCOL_ERROR due to invalid stream identifier
for event in events:
    if isinstance(event, h2.events.RequestReceived):
        if event.stream_id % 2 == 0:  # Even-numbered stream ID detected
            print(f"PROTOCOL_ERROR: Client sent a request with an even-numbered stream ID {event.stream_id}")

conn.close()
sock.close()