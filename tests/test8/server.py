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

# Check for PROTOCOL_ERROR due to duplicate stream ID
stream_ids = set()  # Track used stream IDs
for event in events:
    if isinstance(event, h2.events.RequestReceived):
        stream_id = event.stream_id
        if stream_id in stream_ids:
            print(f"PROTOCOL_ERROR: Stream ID {stream_id} reused!")
            h2_conn.close_connection()
            conn.sendall(h2_conn.data_to_send())
            break
        else:
            stream_ids.add(stream_id)
            print(f"Request received on stream {stream_id}")

conn.close()
sock.close()