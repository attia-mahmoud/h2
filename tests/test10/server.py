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

# Check for FRAME_SIZE_ERROR due to oversized frame
for event in events:
    if isinstance(event, h2.events.DataReceived):
        if len(event.data) > h2_conn.max_inbound_frame_size:
            print(f"FRAME_SIZE_ERROR: Received a frame larger than {h2_conn.max_inbound_frame_size} bytes!")
            h2_conn.close_connection()
            conn.sendall(h2_conn.data_to_send())
            break
    else:
        print(f"Event received: {event}")

conn.close()
sock.close()