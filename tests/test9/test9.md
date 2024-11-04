Scenario: Sending a HEADERS Frame on a Closed Stream

In HTTP/2, after a stream is fully closed, no additional frames should be sent on that stream. If a client attempts to send a HEADERS frame on a stream that has been closed, it creates a non-conformant packet.
