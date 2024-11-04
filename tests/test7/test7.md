Scenario: Sending a Pseudo-Header Field After a Regular Header

In HTTP/2, pseudo-header fields MUST precede regular headers. Sending a pseudo-header field after a regular header makes the packet non-conformant, and the receiver should respond with a PROTOCOL_ERROR.