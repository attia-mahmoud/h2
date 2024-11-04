Scenario: Sending a Non-Conformant HTTP/2 Header
According to RFC 7540 Section 8.1.2.2 (Connection-Specific Header Fields), connection-specific headers such as Connection, Upgrade, Keep-Alive, Proxy-Connection, and Transfer-Encoding MUST NOT be sent in HTTP/2 frames. Sending such a header would make the packet non-conformant.
