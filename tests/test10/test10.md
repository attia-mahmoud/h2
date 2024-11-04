Scenario: Sending a Frame Exceeding the Maximum Frame Size

In HTTP/2, the default maximum frame size is 16,384 bytes (specified by the SETTINGS_MAX_FRAME_SIZE setting), though it can be adjusted by the server. Sending a frame larger than the server’s SETTINGS_MAX_FRAME_SIZE is non-conformant, and the server should respond with a FRAME_SIZE_ERROR.