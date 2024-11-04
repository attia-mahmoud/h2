Scenario: Sending a DATA Frame on a Closed Stream
According to the HTTP/2 specification, once a stream is closed (either half-closed or fully closed), no more DATA frames are allowed on that stream. If the client attempts to send a DATA frame on a closed stream, it’s a non-conformant packet. The server should either reject the frame or throw a STREAM_CLOSED error.
