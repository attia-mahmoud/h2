**Section 3.2 (Starting HTTP/2 for "https" URIs):**
   1. "The 'h2c' protocol identifier MUST NOT be sent by a client or selected by a server. the "h2c" protocol identifier describes a protocol that does not use TLS."
   ✔ 2. "Once TLS negotiation is complete, both the client and the server MUST send a connection preface." (Implemented for client side)

**Section 3.3 (Starting HTTP/2 with Prior Knowledge):**
   3. "A client that knows that a server supports HTTP/2 can establish a TCP connection and send the connection preface (Section 3.4) followed by HTTP/2 frames. Servers can identify these connections by the presence of the connection preface. This only aﬀects the establishment of HTTP/2 connections over cleartext TCP; HTTP/2 connections over TLS use MUST protocol negotiation in TLS [TLS-ALPN]. Likewise, the server send a connection preface (Section 3.4)."

**Section 3.4 (HTTP/2 Connection Preface):**
   ✔ 4. "That is, the connection preface starts with the string "PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n". 
   ✔ 5. "This sequence MUST be followed by a SETTINGS frame (Section 6.5), which can be empty."
   6. "The server connection preface consists of a potentially empty SETTINGS frame (Section 6.5) that MUST be the first frame the server sends in the HTTP/2 connection."
   7. "The SETTINGS frames received from a peer as part of the connection preface MUST be acknowledged (see Section 6.5.3) after sending the connection preface. Clients and servers MUST treat an invalid connection preface as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."

**Section 4.1 (Frame Format):**
   ✔ 8. "Values greater than 214 (16,384) MUST NOT be sent unless the receiver has set a larger value for SETTINGS_MAX_FRAME_SIZE. An endpoint MUST send an error code of FRAME_SIZE_ERROR if a frame exceeds the size defined in SETTINGS_MAX_FRAME_SIZE."
   ✔ 9. "The frame type determines the format and semantics of the frame. Frames defined in this document are listed in Section 6. Implementations MUST ignore and discard frames of unknown types."
   10. "Flags are assigned semantics specific to the indicated frame type. Unused flags are those that have no defined semantics for a particular frame type. Unused flags MUST be ignored on receipt and MUST be left unset (0x00) when sending."
   ✔ 11. "A reserved 1-bit field. The semantics of this bit are undefined, and the bit MUST remain unset (0x00) when sending and MUST be ignored when receiving."

**Section 4.2 (Frame Size):**
   12. "An endpoint MUST be capable of receiving and minimally processing frames up to 2^14 octets in length. A frame size error in a frame that could alter the state of the entire connection MUST be treated as a connection error."

**Section 4.3 (Field Section Compression and Decompression):**
   13. "Field blocks MUST be transmitted as a contiguous sequence of frames, with no interleaved frames of any other type or from any other stream."
   14. "A receiver MUST terminate the connection with a connection error (Section 5.4.1) of type COMPRESSION_ERROR if it does not decompress a field block. A decoding error in a field block MUST be treated as a connection error (Section 5.4.1) of type COMPRESSION_ERROR."

**Section 4.3.1 (Compression State):**
   15. "Once an endpoint acknowledges a change to SETTINGS_HEADER_TABLE_SIZE that reduces the maximum below the current size of the dynamic table, its HPACK encoder MUST start the next field block with a Dynamic Table Size Update instruction that sets the dynamic table to a size that is less than or equal to the reduced maximum. An endpoint MUST treat a field block that follows an acknowledgment of the reduction to the maximum dynamic table size as a connection error (Section 5.4.1) of type COMPRESSION_ERROR if it does not start with a conformant Dynamic Table Size Update instruction."

**Section 5.1 (Stream States):**
    - **idle:**
        ✔ 16. "Receiving any frame other than HEADERS or PRIORITY on a stream in this state MUST be treated as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
        ✔ 17. "If this stream is initiated by the server, as described in Section 5.1.1, then receiving a HEADERS frame MUST also be treated as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    - **reserved:**
        ✔ 18. "An endpoint MUST NOT send any type of frame other than HEADERS, RST_STREAM, or PRIORITY in the reserved (local) state. Receiving any type of frame other than HEADERS, RST_STREAM, or PRIORITY on a stream in the reserved (remote) state MUST be treated as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
        19. "An endpoint MUST NOT send any type of frame other than RST_STREAM, WINDOW_UPDATE, or PRIORITY in the reserved (remote) state. Receiving any type of frame other than RST_STREAM, PRIORITY, or WINDOW_UPDATE on a stream in the reserved (local) state MUST be treated as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    - **half-closed (remote):**
        ✔ 20. "If an endpoint receives additional frames, other than WINDOW_UPDATE, PRIORITY, or RST_STREAM, for a stream that is in the half-closed (remote) state, it MUST respond with a stream error (Section 5.4.2) of type STREAM_CLOSED."
    - **closed:**
        ✔ 21. "An endpoint MUST NOT send frames other than PRIORITY on a closed stream. An endpoint MUST minimally process and then discard any frames it receives in the closed state."

**Section 5.1.1 (Stream Identifiers):**
   ✔ 22. "Streams initiated by a client MUST use odd-numbered stream identifiers;"
   ✔ 23. "Streams initiated by the server MUST use even-numbered stream identifiers."
   ✔ 24. "The identifier of a newly established stream MUST be numerically greater than all streams that the initiating endpoint has opened or reserved. An endpoint that receives an unexpected stream identifier MUST respond with a connection error (Section 5.4.1) of type PROTOCOL_ERROR."


**Section 5.1.2 (Stream Concurrency):**
   25. "Endpoints MUST NOT exceed the limit set by their peer."
   26. "An endpoint that receives a HEADERS frame that causes its advertised concurrent stream limit to be exceeded MUST treat this as a stream error (Section 5.4.2) of type PROTOCOL_ERROR or REFUSED_STREAM."

**Section 5.2.1 (Flow-Control Principles):**
   27. "A sender MUST respect flow-control limits imposed by a receiver."

**Section 5.2.2 (Appropriate Use of Flow Control):**
   28. "Endpoints MUST read and process HTTP/2 frames from the TCP receive buffer as soon as data is available."

**Section 5.4 (Error Handling):**
   29. "If a frame causes a connection error, that error MUST be reported."

**Section 5.4.1 (Connection Error Handling):**
   30. "After sending the GOAWAY frame for an error condition, the endpoint MUST close the TCP connection."

**Section 5.4.2 (Stream Error Handling):**
   31. "The peer that sends the RST_STREAM frame MUST be prepared to receive any frames that were sent or enqueued for sending by the remote peer."
   ✔ 32. "To avoid looping, an endpoint MUST NOT send a RST_STREAM in response to a RST_STREAM frame."

**Section 5.5 (Extending HTTP/2):**
   33. "Implementations MUST ignore unknown or unsupported values in all extensible protocol elements."
   ✔ 34. "Implementations MUST discard frames that have unknown or unsupported types."
   35. "However, extension frames that appear in the middle of a field block (Section 4.3) are not permitted; these MUST be treated as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
   36. "An extension that changes existing protocol elements or state MUST be negotiated before being used."
   37. "If a setting is used for extension negotiation, the initial value MUST be defined in such a fashion that the extension is initially disabled."

**Section 6.1 (DATA Frames):**
    **Padding:**
        38. "Padding octets MUST be set to zero when sending DATA frames."
   ✔ 39. "DATA frames MUST be associated with a stream."
   ✔ 40. "If a DATA frame is received whose Stream Identifier field is 0x00, the recipient MUST respond with a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
   ✔ 41. "If a DATA frame is received whose stream is not in the "open" or "half-closed (local)" state, the recipient MUST respond with a stream error (Section 5.4.2) of type STREAM_CLOSED."
   42. "If the length of the padding is the length of the frame payload or greater, the recipient MUST treat this as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."

**Section 6.2 (HEADERS Frame):**
    **Padding:**
        43. "Padding octets MUST be set to zero when sending."
    **END_HEADERS (0x04):**
        ✔ 44. "A HEADERS frame without the END_HEADERS flag set MUST be followed by a CONTINUATION frame for the same stream. A receiver MUST treat the receipt of any other type of frame or a frame on a different stream as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
   45. "HEADERS frames MUST be associated with a stream."
   ✔ 46. "If a HEADERS frame is received whose Stream Identifier field is 0x00, the recipient MUST respond with a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
   47. "If the length of the padding is the length of the frame payload or greater, the recipient MUST treat this as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."

**Section 6.3 (PRIORITY Frame):**
    ✔ 48. "If a PRIORITY frame is received with a stream identifier of 0x00, the recipient MUST respond with a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    49. "A PRIORITY frame with a length other than 5 octets MUST be treated as a stream error (Section 5.4.2) of type FRAME_SIZE_ERROR."

**Section 6.4 (RST_STREAM Frame):**
    ✔ 50. "After receiving a RST_STREAM on a stream, the receiver MUST NOT send additional frames for that stream, except for PRIORITY."
    51. "However, after sending the RST_STREAM, the sending endpoint MUST be prepared to receive and process additional frames sent on the stream that might have been sent by the peer prior to the arrival of the RST_STREAM."
    ✔52. "RST_STREAM frames MUST be associated with a stream."
    ✔ 53. "If a RST_STREAM frame is received with a stream identifier of 0x00, the recipient MUST treat this as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    ✔ 54. "RST_STREAM frames MUST NOT be sent for a stream in the "idle" state. If a RST_STREAM frame identifying an idle stream is received, the recipient MUST treat this as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    ✔ 55. "A RST_STREAM frame with a length other than 4 octets MUST be treated as a connection error (Section 5.4.1) of type FRAME_SIZE_ERROR."

**Section 6.5 (SETTINGS Frame):**
    ✔ 56. "A SETTINGS frame MUST be sent by both endpoints at the start of a connection and MAY be sent at any other time by either endpoint over the lifetime of the connection."
    57. "Implementations MUST support all of the settings defined by this specification."
    - **ACK (0x01):**
        ✔ 58. "When set, the ACK flag indicates that this frame acknowledges receipt and application of the peer's SETTINGS frame. When this bit is set, the frame payload of the SETTINGS frame MUST be empty. Receipt of a SETTINGS frame with the ACK flag set and a length field value other than 0 MUST be treated as a connection error (Section 5.4.1) of type FRAME_SIZE_ERROR."
    ✔ 59. "The stream identifier for a SETTINGS frame MUST be zero (0x00). If an endpoint receives a SETTINGS frame whose Stream Identifier field is anything other than 0x00, the endpoint MUST respond with a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    ✔ 60. "A SETTINGS frame with a length other than a multiple of 6 octets MUST be treated as a connection error (Section 5.4.1) of type FRAME_SIZE_ERROR. A badly formed or incomplete SETTINGS frame MUST be treated as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."

**Section 6.5.2 (Defined Settings):**
    - **SETTINGS_ENABLE_PUSH (0x02):**
        ✔ 61. "A server MUST NOT send a PUSH_PROMISE frame if it receives the SETTINGS_ENABLE_PUSH (0x02) parameter set to a value of 0. A client that has both set this parameter to 0 and had it acknowledged MUST treat the receipt of a PUSH_PROMISE frame as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
        ✔ 62. "The initial value of SETTINGS_ENABLE_PUSH is 1. Any value other than 0 or 1 MUST be treated as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
        ✔ 63. "A server MUST NOT explicitly set this value (SETTINGS_ENABLE_PUSH) to 1. A server MAY choose to omit this setting (SETTINGS_ENABLE_PUSH) when it sends a SETTINGS frame, but if a server does include a value, it MUST be 0. A client MUST treat receipt of a SETTINGS frame with SETTINGS_ENABLE_PUSH set to 1 as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    - **SETTINGS_INITIAL_WINDOW_SIZE (0x04):**
        ✔ 64. "Values above the maximum flow-control window size of 231-1 MUST be treated as a connection error (Section 5.4.1) of type FLOW_CONTROL_ERROR."
    - **SETTINGS_MAX_FRAME_SIZE (0x05):**
        ✔ 65. "The initial value is 214 (16,384) octets. The value advertised by an endpoint MUST be between this initial value and the maximum allowed frame size (224-1 or 16,777,215 octets), inclusive. Values outside this range MUST be treated as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    ✔ 66. "An endpoint that receives a SETTINGS frame with any unknown or unsupported identifier MUST ignore that setting."

**Section 6.5.3 (Settings Synchronization):**
    67. "In order to provide such synchronization timepoints, the recipient of a SETTINGS frame in which the ACK flag is not set MUST apply the updated settings as soon as possible upon receipt."
    68. "The values in the SETTINGS frame MUST be processed in the order they appear, with no other frame processing between values."
    ✔ 69. "Unsupported settings MUST be ignored."
    70. "Once all values have been processed, the recipient MUST immediately emit a SETTINGS frame with the ACK flag set."

**Section 6.6 (PUSH_PROMISE Frame):**
    - **Promised Stream ID:**
        ✔ 71. "The promised stream identifier MUST be a valid choice for the next stream sent by the sender (see "new stream identifier" in Section 5.1.1)."
    - **Padding:**
        72. "Padding octets MUST be set to zero when sending."
    - **END_HEADERS (0x04):**
        ✔ 73. "A PUSH_PROMISE frame without the END_HEADERS flag set MUST be followed by a CONTINUATION frame for the same stream. A receiver MUST treat the receipt of any other type of frame or a frame on a different stream as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    ✔ 74. "A sender MUST NOT send a PUSH_PROMISE on a stream unless that stream is either "open" or "half-closed (remote). PUSH_PROMISE frames MUST only be sent on a peer-initiated stream that is in either the "open" or "half-closed (remote)" state."
    ✔ 75. "If the Stream Identifier field specifies the value 0x00, a recipient MUST respond with a connection error (Section 5.4.1) of type PROTOCOL_ERROR. A receiver MUST treat the receipt of a PUSH_PROMISE that promises an illegal stream identifier (Section 5.1.1) as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    ✔ 76. "PUSH_PROMISE MUST NOT be sent if the SETTINGS_ENABLE_PUSH setting of the peer endpoint is set to 0. An endpoint that has set this setting and has received acknowledgment MUST treat the receipt of a PUSH_PROMISE frame as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    ✔ 77. "the sender MUST ensure that the promised stream is a valid choice for a new stream identifier (Section 5.1.1) (that is, the promised stream MUST be in the "idle" state)."
    78. "However, an endpoint that has sent RST_STREAM on the associated stream MUST handle PUSH_PROMISE frames that might have been created before the RST_STREAM frame is received and processed."
    79. "If the length of the padding is the length of the frame payload or greater, the recipient MUST treat this as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."

**Section 6.7 (PING Frame):**
    ✔ 80. "In addition to the frame header, PING frames MUST contain 8 octets of opaque data in the frame payload. Receipt of a PING frame with a length field value other than 8 MUST be treated as a connection error (Section 5.4.1) of type FRAME_SIZE_ERROR."
    81. "Receivers of a PING frame that does not include an ACK flag MUST send a PING frame with the ACK flag set in response, with an identical frame payload."
    - **ACK (0x01):**
        82. "An endpoint MUST set this flag in PING responses."
        83. "An endpoint MUST NOT respond to PING frames containing this flag."
    ✔ 84. "If a PING frame is received with a Stream Identifier field value other than 0x00, the recipient MUST respond with a connection error (Section 5.4.1) of type PROTOCOL_ERROR."

**Section 6.8 (GOAWAY Frame):**
    ✔ 85. "Receivers of a GOAWAY frame MUST NOT open additional streams on the connection, although a new connection can be established for new streams."
    ✔ 86. "An endpoint MUST treat a GOAWAY frame with a stream identifier other than 0x00 as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    87. "Endpoints MUST NOT increase the value they send in the last stream identifier, since the peers might already have retried unprocessed requests on another connection."
    88. "For instance, HEADERS, PUSH_PROMISE, and CONTINUATION frames MUST be minimally processed to ensure that the state maintained for field section compression is consistent (see Section 4.3); similarly, DATA frames MUST be counted toward the connection flow-control window."
    89. "Logged or otherwise persistently stored debug data MUST have adequate safeguards to prevent unauthorized access."

**Section 6.9 (WINDOW_UPDATE Frame):**
    90. "Flow control only applies to frames that are identified as being subject to flow control. Of the frame types defined in this document, this includes only DATA frames. Frames that are exempt from flow control MUST be accepted and processed, unless the receiver is unable to assign resources to handling the frame."
    ✔ 91. "A receiver MUST treat the receipt of a WINDOW_UPDATE frame with a flow-control window increment of 0 as a stream error (Section 5.4.2) of type PROTOCOL_ERROR; errors on the connection flow-control window MUST be treated as a connection error (Section 5.4.1)."
    92. "WINDOW_UPDATE can be sent by a peer that has sent a frame with the END_STREAM flag set. This means that a receiver could receive a WINDOW_UPDATE frame on a stream in a "half-closed (remote)" or "closed" state. A receiver MUST NOT treat this as an error (see Section 5.1)."
    93. "A receiver that receives a flow-controlled frame MUST always account for its contribution against the connection flow-control window, unless the receiver treats this as a connection error (Section 5.4.1)."
    94. "A WINDOW_UPDATE frame with a length other than 4 octets MUST be treated as a connection error (Section 5.4.1) of type FRAME_SIZE_ERROR."

**Section 6.9.1 (The Flow-Control Window):**
    ✔ 95. "The sender MUST NOT send a flow-controlled frame with a length that exceeds the space available in either of the flow-control windows advertised by the receiver."
    ✔ 96. "A sender MUST NOT allow a flow-control window to exceed 2^31-1 octets. If a sender receives a WINDOW_UPDATE that causes a flow-control window to exceed this maximum, it MUST terminate either the stream or the connection, as appropriate."

**Section 6.9.2 (Initial Flow-Control Window Size):**
    97. "When the value of SETTINGS_INITIAL_WINDOW_SIZE changes, a receiver MUST adjust the size of all stream flow-control windows that it maintains by the difference between the new value and the old value."
    98. "A sender MUST track the negative flow-control window and MUST NOT send new flow-controlled frames until it receives WINDOW_UPDATE frames that cause the flow-control window to become positive."
    ✔ 99. "An endpoint MUST treat a change to SETTINGS_INITIAL_WINDOW_SIZE that causes any flow-control window to exceed the maximum size as a connection error (Section 5.4.1) of type FLOW_CONTROL_ERROR."

**Section 6.9.3 (Reducing the Stream Window Size):**
    100. "A receiver that wishes to use a smaller flow-control window than the current size can send a new SETTINGS frame. However, the receiver MUST be prepared to receive data that exceeds this window size, since the sender might send data that exceeds the lower limit prior to processing the SETTINGS frame."

**Section 6.10 (CONTINUATION Frame):**
    - **END_HEADERS (0x04):**
        ✔ 101. "If the END_HEADERS flag is not set, this frame MUST be followed by another CONTINUATION frame. A receiver MUST treat the receipt of any other type of frame or a frame on a different stream as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    ✔ 102. "CONTINUATION frames MUST be associated with a stream."
    ✔ 103. "If a CONTINUATION frame is received with a Stream Identifier field of 0x00, the recipient MUST respond with a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    ✔ 104. "A CONTINUATION frame MUST be preceded by a HEADERS, PUSH_PROMISE or CONTINUATION frame without the END_HEADERS flag set. A recipient that observes violation of this rule MUST respond with a connection error (Section 5.4.1) of type PROTOCOL_ERROR."

**Section 7 (Error Codes):**
    105. "Unknown or unsupported error codes MUST NOT trigger any special behavior. These MAY be treated by an implementation as being equivalent to INTERNAL_ERROR."

**Section 8.1 (HTTP Message Framing):**
    ✔ 106. "Other frames (from any stream) MUST NOT occur between the HEADERS frame and any CONTINUATION frames that might follow."
    ✔ 107. "Trailers MUST NOT include pseudo-header fields (Section 8.3). An endpoint that receives pseudo-header fields in trailers MUST treat the request or response as malformed (Section 8.1.1)."
    ✔ 108. "An endpoint that receives a HEADERS frame without the END_STREAM flag set after receiving the HEADERS frame that opens a request or after receiving a final (non-informational) status code MUST treat the corresponding request or response as malformed (Section 8.1.1)."
    109. "Clients MUST NOT discard responses as a result of receiving such a RST_STREAM, though clients can always discard responses at their discretion for other reasons."

**Section 8.1.1 (Malformed Messages):**
    110. "Intermediaries that process HTTP requests or responses (i.e., any intermediary not acting as a tunnel) MUST NOT forward a malformed request or response. Malformed requests or responses that are detected MUST be treated as a stream error (Section 5.4.2) of type PROTOCOL_ERROR."
    111. "For malformed requests, a server MAY send an HTTP response prior to closing or resetting the stream. Clients MUST NOT accept a malformed response."

**Section 8.2 (HTTP Fields):**
    ✔ 112. "Field names MUST be converted to lowercase when constructing an HTTP/2 message."

**Section 8.2.1 (Field Validity):**
    ✔ 113. "A field name MUST NOT contain characters in the ranges 0x00-0x20, 0x41-0x5a, or 0x7f-0xff (all ranges inclusive). This specifically excludes all non-visible ASCII characters, ASCII SP (0x20), and uppercase characters ('A' to 'Z', ASCII 0x41 to 0x5a)."
    ✔ 114. "With the exception of pseudo-header fields (Section 8.3), which have a name that starts with a single colon, field names MUST NOT include a colon (ASCII COLON, 0x3a)."
    ✔ 115. "A field value MUST NOT contain the zero value (ASCII NUL, 0x00), line feed (ASCII LF, 0x0a), or carriage return (ASCII CR, 0x0d) at any position."
    ✔ 116. "A field value MUST NOT start or end with an ASCII whitespace character (ASCII SP or HTAB, 0x20 or 0x09). A request or response that contains a field that violates any of these conditions MUST be treated as malformed (Section 8.1.1). In particular, an intermediary that does not process fields when forwarding messages MUST NOT forward fields that contain any of the values that are listed as prohibited above."

**Section 8.2.2 (Connection-Specific Header Fields):**
    ✔ 117. "An endpoint MUST NOT generate an HTTP/2 message containing connection-specific header fields. This includes the Connection header field and those listed as having connection-specific semantics in Section 7.6.1 of [HTTP] (that is, Proxy-Connection, Keep-Alive, Transfer-Encoding, and Upgrade). Any message containing connection-specific header fields MUST be treated as malformed (Section 8.1.1)."
    118. "The only exception to this is the TE header field, which MAY be present in an HTTP/2 request; when it is, it MUST NOT contain any value other than "trailers"."
    119. "An intermediary transforming an HTTP/1.x message to HTTP/2 MUST remove connection-specific header fields as discussed in Section 7.6.1 of [HTTP], or their messages will be treated by other HTTP/2 endpoints as malformed (Section 8.1.1)."

**Section 8.2.3 (Compressing the Cookie Header Field):**
    120. "The Cookie header field MUST NOT be compressed."
    121. "If there are multiple Cookie header fields after decompression, these MUST be concatenated into a single octet string using the two-octet delimiter of 0x3b, 0x20 (the ASCII string "; ") before being passed into a non-HTTP/2 context, such as an HTTP/1.1 connection, or a generic HTTP server application."

**Section 8.3 (HTTP Control Data):**
    ✔ 122. "Pseudo-header fields are not HTTP header fields. Endpoints MUST NOT generate pseudo-header fields other than those defined in this document."
    ✔ 123. "Pseudo-header fields defined for requests MUST NOT appear in responses."
    ✔ 124. "Pseudo-header fields defined for responses MUST NOT appear in requests."
    ✔ 125. "Pseudo-header fields MUST NOT appear in a trailer section. Endpoints MUST treat a request or response that contains undefined or invalid pseudo-header fields as malformed (Section 8.1.1)."
    ✔ 126. "All pseudo-header fields MUST appear in a field block before all regular field lines. Any request or response that contains a pseudo-header field that appears in a field block after a regular field line MUST be treated as malformed (Section 8.1.1)."
    ✔ 127. "The same pseudo-header field name MUST NOT appear more than once in a field block. A field block for an HTTP request or response that contains a repeated pseudo-header field name MUST be treated as malformed (Section 8.1.1)."

**Section 8.3.1 (Request Pseudo-Header Fields):**
    - **:authority**
        128. "The ":authority" pseudo-header field conveys the authority portion (Section 3.2 of [RFC3986]) of the target URI (Section 7.1 of [HTTP]). The recipient of an HTTP/2 request MUST NOT use the Host header field to determine the target URI if ":authority" is present."
        129. "Clients that generate HTTP/2 requests directly MUST use the ":authority" pseudo-header field to convey authority information, unless there is no authority information to convey (in which case it MUST NOT generate ":authority")."
        ✔ 130. "Clients MUST NOT generate a request with a Host header field that differs from the ":authority" pseudo-header field."
        131. "An origin server can apply any normalization method, whereas other servers MUST perform scheme-based normalization (see Section 6.2.3 of [RFC3986]) of the two fields."
        132. "An intermediary that forwards a request over HTTP/2 MUST construct an ":authority" pseudo-header field using the authority information from the control data of the original request, unless the original request's target URI does not contain authority information (in which case it MUST NOT generate ":authority")."
        133. "An intermediary that needs to generate a Host header field (which might be necessary to construct an HTTP/1.1 request) MUST use the value from the ":authority" pseudo-header field as the value of the Host field, unless the intermediary also changes the request target. This replaces any existing Host field to avoid potential vulnerabilities in HTTP routing."
        ✔ 134. "':authority' MUST NOT include the deprecated userinfo subcomponent for "http" or "https" schemed URIs."
    - **:path**
        ✔ 135. "The ":path" pseudo-header field conveys the path portion (Section 3.3 of [RFC3986]) of the target URI (Section 7.1 of [HTTP]). This pseudo-header field MUST NOT be empty for "http" or "https" URIs; "http" or "https" URIs that do not contain a path component MUST include a value of '/'. The exceptions to this rule are: an OPTIONS request for an "http" or "https" URI that does not include a path component; these MUST include a ":path" pseudo-header field with a value of '*' (see Section 7.1 of [HTTP])."
    ✔ 136. "All HTTP/2 requests MUST include exactly one valid value for the ":method", ":scheme", and ":path" pseudo-header fields, unless they are CONNECT requests (Section 8.5). An HTTP request that omits mandatory pseudo-header fields is malformed (Section 8.1.1)."

**Section 8.3.2 (Response Pseudo-Header Fields):**
    ✔ 137. "For HTTP/2 responses, a single ":status" pseudo-header field is defined that carries the HTTP status code field (see Section 15 of [HTTP]). This pseudo-header field MUST be included in all responses, including interim responses; otherwise, the response is malformed (Section 8.1.1)."

**Section 8.4 (Server Push):**
    ✔ 138. "Promised requests MUST be safe (see Section 9.2.1 of [HTTP]) and cacheable (see Section 9.2.3 of [HTTP])."
    139. "Promised requests cannot include any content or a trailer section. Clients that receive a promised request that is not cacheable, that is not known to be safe, or that indicates the presence of request content MUST reset the promised stream with a stream error (Section 5.4.2) of type PROTOCOL_ERROR."
    140. "Pushed responses that are not cacheable MUST NOT be stored by any HTTP cache."
    141. "The server MUST include a value in the ":authority" pseudo-header field for which the server is authoritative (see Section 10.1)."
    142. "A client MUST treat a PUSH_PROMISE for which the server is not authoritative as a stream error (Section 5.4.2) of type PROTOCOL_ERROR."
    ✔ 143. "A client cannot push. Thus, servers MUST treat the receipt of a PUSH_PROMISE frame as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."

**Section 8.4.1 (Push Requests):**
    ✔ 144. "The header fields in PUSH_PROMISE and any subsequent CONTINUATION frames MUST be a valid and complete set of request header fields (Section 8.3.1)."
    ✔ 145. "The server MUST include a method in the ":method" pseudo-header field that is safe and cacheable. If a client receives a PUSH_PROMISE that does not include a complete and valid set of header fields or the ":method" pseudo-header field identifies a method that is not safe, it MUST respond on the promised stream with a stream error (Section 5.4.2) of type PROTOCOL_ERROR."
    ✔ 146. "PUSH_PROMISE frames MUST NOT be sent by the client."
    ✔ 147. "PUSH_PROMISE frames can be sent by the server on any client-initiated stream, but the stream MUST be in either the "open" or "half-closed (remote)" state with respect to the server."
    148. "Clients receiving a pushed response MUST validate that either the server is authoritative (see Section 10.1) or the proxy that provided the pushed response is configured for the corresponding request."

**Section 8.5 (The CONNECT Method):**
    ✔ 149. "The ":scheme" and ":path" pseudo-header fields MUST be omitted."
    150. "Frame types other than DATA or stream management frames (RST_STREAM, WINDOW_UPDATE, and PRIORITY) MUST NOT be sent on a connected stream and MUST be treated as a stream error (Section 5.4.2) if received."
    151. "A TCP connection error is signaled with RST_STREAM. A proxy treats any error in the TCP connection, which includes receiving a TCP segment with the RST bit set, as a stream error (Section 5.4.2) of type CONNECT_ERROR. Correspondingly, a proxy MUST send a TCP segment with the RST bit set if it detects an error with the stream or the HTTP/2 connection."

**Section 8.7 (Request Reliability):**
    152. "A server MUST NOT indicate that a stream has not been processed unless it can guarantee that fact."
    153. "If frames that are on a stream are passed to the application layer for any stream, then REFUSED_STREAM MUST NOT be used for that stream, and a GOAWAY frame MUST include a stream identifier that is greater than or equal to the given stream identifier."

**Section 9.1.1 (Connection Reuse):**
    154. "The certificate presented by the server MUST satisfy any checks that the client would perform when forming a new TLS connection for the host in the URI."

**Section 9.2 (Use of TLS Features):**
    155. "Implementations of HTTP/2 MUST use TLS version 1.2 [TLS12] or higher for HTTP/2 over TLS. The general TLS usage guidance in [TLSBCP] SHOULD be followed, with some additional restrictions that are specific to HTTP/2."
    156. "The TLS implementation MUST support the Server Name Indication (SNI) [TLS-EXT] extension to TLS."
    157. "If the server is identified by a domain name [DNS-TERMS], clients MUST send the server_name TLS extension unless an alternative mechanism to indicate the target host is used."

**Section 9.2.1 (TLS 1.2 Features):**
    158. "A deployment of HTTP/2 over TLS 1.2 MUST disable compression."
    159. "A deployment of HTTP/2 over TLS 1.2 MUST disable renegotiation. An endpoint MUST treat a TLS renegotiation as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."
    160. "An endpoint MAY use renegotiation to provide confidentiality protection for client credentials offered in the handshake, but any renegotiation MUST occur prior to sending the connection preface."
    161. "Implementations MUST support ephemeral key exchange sizes of at least 2048 bits for cipher suites that use ephemeral finite field Diffie-Hellman (DHE) (Section 8.1.2 of [TLS12]) and 224 bits for cipher suites that use ephemeral elliptic curve Diffie-Hellman (ECDHE) [RFC8422]."
    162. "Clients MUST accept DHE sizes of up to 4096 bits."

**Section 9.2.2 (TLS 1.2 Cipher Suites):**
    163. "Endpoints MAY choose to generate a connection error (Section 5.4.1) of type INADEQUATE_SECURITY if one of the prohibited cipher suites is negotiated. A deployment that chooses to use a prohibited cipher suite risks triggering a connection error unless the set of potential peers is known to accept that cipher suite. Implementations MUST NOT generate this error in reaction to the negotiation of a cipher suite that is not prohibited."
    164. "The list of prohibited cipher suites includes the cipher suite that TLS 1.2 makes mandatory, which means that TLS 1.2 deployments could have non-intersecting sets of permitted cipher suites. To avoid this problem, which causes TLS handshake failures, deployments of HTTP/2 that use TLS 1.2 MUST support TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256 [TLS-ECDHE] with the P-256 elliptic curve [RFC8422]."

**Section 9.2.3 (TLS 1.3 Features):**
    165. "HTTP/2 servers MUST NOT send post-handshake TLS 1.3 CertificateRequest messages."
    166. "HTTP/2 clients MUST treat a TLS post-handshake CertificateRequest message as a connection error (Section 5.4.1) of type PROTOCOL_ERROR."

**Section 10.3 (Intermediary Encapsulation Attacks):**
    167. "An intermediary that translates an HTTP/2 request or response MUST validate fields according to the rules in Section 8.2 before translating a message to another HTTP version."
    168. "An intermediary that receives any fields that require removal before forwarding (see Section 7.6.1 of [HTTP]) MUST remove or replace those header fields when forwarding messages."

**Section 10.4 (Cacheability of Pushed Responses):**
    169. "Where multiple tenants share space on the same server, that server MUST ensure that tenants are not able to push representations of resources that they do not have authority over."
    170. "Pushed responses for which an origin server is not authoritative (see Section 10.1) MUST NOT be used or cached."

**Section 10.5.1 (Limits on Field Block Size):**
    171. "A server that receives a larger field block than it is willing to handle can send an HTTP 431 (Request Header Fields Too Large) status code [RFC6585]. A client can discard responses that it cannot process. The field block MUST be processed to ensure a consistent connection state, unless the connection is closed."

**Section 10.6 (Use of Compression):**
    172. "Implementations communicating on a secure channel MUST NOT compress content that includes both confidential and attacker-controlled data unless separate compression dictionaries are used for each source of data."
    173. "Compression MUST NOT be used if the source of data cannot be reliably determined."
    174. "Generic stream compression, such as that provided by TLS, MUST NOT be used with HTTP/2 (see Section 9.2)."