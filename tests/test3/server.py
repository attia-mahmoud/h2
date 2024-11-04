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

# Check for STREAM_CLOSED error or non-conformant DATA frame
for event in events:
    if isinstance(event, h2.events.DataReceived):
        print(f"Received data: {event.data}")
        if h2_conn.streams[event.stream_id].state == h2.stream.StreamState.CLOSED:
            print("STREAM_CLOSED error: Data received on closed stream!")
    elif isinstance(event, h2.events.StreamEnded):
        print(f"Stream {event.stream_id} ended.")

conn.close()
sock.close()