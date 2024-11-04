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

# Check for STREAM_CLOSED error due to sending a HEADERS frame on a closed stream
for event in events:
    if isinstance(event, h2.events.RequestReceived):
        print(f"Request received on stream {event.stream_id}")
    if isinstance(event, h2.events.StreamEnded):
        print(f"Stream {event.stream_id} ended.")
    if isinstance(event, h2.events.HeadersReceived):
        # If we receive headers on a closed stream, that's an error
        stream_id = event.stream_id
        if h2_conn.streams[stream_id].state == h2.stream.StreamState.CLOSED:
            print(f"STREAM_CLOSED error: Headers received on closed stream {stream_id}")
            h2_conn.close_connection()
            conn.sendall(h2_conn.data_to_send())
            break

conn.close()
sock.close()