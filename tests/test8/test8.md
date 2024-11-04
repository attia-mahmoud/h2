Scenario: Reusing a Stream ID for a New Request

In HTTP/2, each stream initiated by a client must use a new, unique, odd-numbered stream ID. Reusing the same stream ID for multiple requests on different streams is non-conformant and should trigger an error.