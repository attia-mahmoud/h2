import h2.connection
import h2.events
import h2.config
import socket
import time
import json
import sys

def load_test_headers(test_id):
    with open('variables.json', 'r') as f:
        test_cases = json.load(f)
        test = next((t for t in test_cases['test_cases'] if t['id'] == test_id), None)
        if test is None:
            print(f"Test {test_id} not found")
            sys.exit(1)
        print(f"\nRunning test: {test['category']}")
        print(f"Description: {test['description']}")
        return test['headers']

def main():
    # Create a TCP connection
    headers = load_test_headers(148)

    sock = socket.create_connection(('localhost', 7700))
    print("Connected to proxy server")
    
    # Create an H2 connection
    config = h2.config.H2Configuration(client_side=True)
    conn = h2.connection.H2Connection(config=config)
    
    # Start the connection
    conn.initiate_connection()
    sock.sendall(conn.data_to_send())
    

    # Send request headers
    # headers = [
    #     (':method', 'GET'),
    #     (':scheme', 'http'),
    #     (':authority', 'localhost'),
    #     (':path', '/'),
    #     ('user-agent', 'python-h2'),
    #     ('accept', '*/*'),
    #     ('connection', 'keep-alive')
    # ]
    
    stream_id = conn.get_next_available_stream_id()
    conn.send_headers(stream_id, headers, end_stream=True)
    sock.sendall(conn.data_to_send())
    
    response_data = b''
    try:
        while True:
            data = sock.recv(65535)
            if not data:
                break
                
            print(f"Received data: {len(data)} bytes")
            events = conn.receive_data(data)
            
            for event in events:
                print(f"Event: {event}")
                
                if isinstance(event, h2.events.ResponseReceived):
                    print(f"Response headers: {event.headers}")
                
                elif isinstance(event, h2.events.DataReceived):
                    response_data += event.data
                    conn.acknowledge_received_data(
                        event.flow_controlled_length, 
                        event.stream_id
                    )
                    
                elif isinstance(event, h2.events.StreamEnded):
                    print(f"Stream {event.stream_id} ended")
                    return
                    
            outbound_data = conn.data_to_send()
            if outbound_data:
                sock.sendall(outbound_data)
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()
        
    if response_data:
        print(f"Response: {response_data.decode('utf-8')}")

if __name__ == '__main__':
    main()