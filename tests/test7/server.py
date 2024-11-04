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

# Check for PROTOCOL_ERROR due to invalid pseudo-header ordering
for event in events:
    if isinstance(event, h2.events.RequestReceived):
        print("Received headers:", event.headers)
        # Validate header order: if a regular header appears before a pseudo-header, it's non-conformant
        pseudo_header_seen = False
        for header in event.headers:
            if header[0].startswith(':'):
                pseudo_header_seen = True
            elif pseudo_header_seen and not header[0].startswith(':'):
                print("PROTOCOL_ERROR: Regular header before pseudo-header detected!")
                h2_conn.close_connection()
                conn.sendall(h2_conn.data_to_send())
                break

conn.close()
sock.close()