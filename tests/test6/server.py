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

# Check for COMPRESSION_ERROR due to invalid dynamic table size update
for event in events:
    print(f"Event received: {event}")
    if isinstance(event, h2.events.WindowUpdated):
        print(f"Window updated: Stream {event.stream_id}, Window size: {event.delta}")
    print(f"Settings received: {h2_conn.remote_settings}")
    if isinstance(event, h2.events.RequestReceived):
        try:
            headers = dict(event.headers)
            print("Received headers:", headers)
        except h2.exceptions.CompressionError:
            print("COMPRESSION_ERROR: Invalid dynamic table size update detected!")
            h2_conn.close_connection()
            conn.sendall(h2_conn.data_to_send())

conn.close()
sock.close()