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

# Check for FLOW_CONTROL_ERROR or invalid WINDOW_UPDATE
for event in events:
    if isinstance(event, h2.events.WindowUpdated):
        print(f"Window updated for stream {event.stream_id}: {event.delta}")
        if h2_conn.remote_flow_control_window(event.stream_id) < 0:
            print("FLOW_CONTROL_ERROR: Flow control window reduced below the outstanding data!")

conn.close()
sock.close()