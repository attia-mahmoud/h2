import h2.connection
import socket
import h2.config
import h2.events

print("Starting server...")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('localhost', 7700))
sock.listen(5)
print("Server listening on port 7700")

while True:
    print("Waiting for connection...")
    conn, addr = sock.accept()
    print(f"Connection received from {addr}")
    
    h2_conn = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=False))
    h2_conn.initiate_connection()
    conn.sendall(h2_conn.data_to_send())

    try:
        while True:
            data = conn.recv(65535)
            if not data:
                print("No data received, connection closed")
                break
                
            print(f"Received data: {data}")
            events = h2_conn.receive_data(data)
            
            for event in events:
                print(f"Event received: {event}")
                if isinstance(event, h2.events.RequestReceived):
                    print("Headers received:", event.headers)
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        conn.close()
        print("Connection closed")

sock.close()