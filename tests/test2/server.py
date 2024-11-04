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

# Check for FLOW_CONTROL_ERROR or oversized DATA frame
for event in events:
    if isinstance(event, h2.events.DataReceived):
        print(f"Received data: {len(event.data)} bytes")
        if len(event.data) > h2_conn.remote_flow_control_window(1):
            print("FLOW_CONTROL_ERROR: Data exceeds flow control window!")
    elif isinstance(event, h2.events.WindowUpdated):
        print(f"Updated window: {event.delta}")

conn.close()
sock.close()