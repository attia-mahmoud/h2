import h2.connection
import h2.config
import h2.events
import socket

def create_response_headers(stream_id):
    return [
        (':status', '200'),
        ('content-type', 'text/plain'),
        ('content-length', str(len('Hello, World!')))
    ]

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('localhost', 7700))
    sock.listen(5)
    
    print(f"Server listening on port 7700")
    
    while True:
        client_socket, addr = sock.accept()
        print(f"Connection from {addr}")
        
        config = h2.config.H2Configuration(client_side=False)
        conn = h2.connection.H2Connection(config=config)
        conn.initiate_connection()
        
        # Send initial settings
        client_socket.sendall(conn.data_to_send())
        
        try:
            while True:
                data = client_socket.recv(65535)
                if not data:
                    break
                
                print(f"Received data: {len(data)} bytes")
                
                events = conn.receive_data(data)
                
                for event in events:
                    print(f"Event: {event}")
                    
                    if isinstance(event, h2.events.RequestReceived):
                        print(f"Request headers: {event.headers}")
                        
                        # Send response headers
                        conn.send_headers(
                            stream_id=event.stream_id,
                            headers=create_response_headers(event.stream_id),
                            end_stream=False
                        )
                        
                        # Send response data
                        response_data = 'Hello, World!'.encode('utf-8')
                        conn.send_data(
                            stream_id=event.stream_id,
                            data=response_data,
                            end_stream=True
                        )
                        
                        client_socket.sendall(conn.data_to_send())
                
                outbound_data = conn.data_to_send()
                if outbound_data:
                    client_socket.sendall(outbound_data)
                    
        except Exception as e:
            print(f"Error: {e}")
        finally:
            client_socket.close()
            print("Connection closed")

if __name__ == '__main__':
    main()