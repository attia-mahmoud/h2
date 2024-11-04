import h2.connection
import h2.config
import socket
import threading

def handle_connection(client_sock, client_addr):
    # Initialize connection to client
    client_h2_conn = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=False))
    client_h2_conn.initiate_connection()
    client_sock.sendall(client_h2_conn.data_to_send())

    # Connect to backend server
    server_sock = socket.create_connection(('localhost', 7700))
    server_h2_conn = h2.connection.H2Connection()
    server_h2_conn.initiate_connection()
    server_sock.sendall(server_h2_conn.data_to_send())

    try:
        while True:
            # Receive data from client
            client_data = client_sock.recv(65535)
            if not client_data:
                break

            # Forward to server
            events = client_h2_conn.receive_data(client_data)
            for event in events:
                if isinstance(event, h2.events.RequestReceived):
                    # Forward the headers to the server
                    server_h2_conn.send_headers(event.stream_id, event.headers)
                    server_sock.sendall(server_h2_conn.data_to_send())

            # Receive server response and forward to client
            server_data = server_sock.recv(65535)
            if server_data:
                client_sock.sendall(server_data)

    finally:
        client_sock.close()
        server_sock.close()

def main():
    proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_sock.bind(('localhost', 7701))  # Proxy runs on port 7701
    proxy_sock.listen(5)
    
    print("Proxy listening on port 7701")
    
    try:
        while True:
            client_sock, client_addr = proxy_sock.accept()
            thread = threading.Thread(target=handle_connection, args=(client_sock, client_addr))
            thread.start()
    finally:
        proxy_sock.close()

if __name__ == "__main__":
    main()