Scenario: Violating Flow-Control Window Limits
In HTTP/2, the flow control mechanism ensures that the sender does not overwhelm the receiver by sending more data than the receiver is willing to accept. The receiver sends WINDOW_UPDATE frames to update how many bytes it can handle. If the sender sends more data than allowed by the flow-control window, it’s a non-conformant packet.
