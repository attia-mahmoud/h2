# Example Test Case

```yaml
test_suites:
  - name: "Connection-Specific Header Fields"
    section: "8.2.2"
    cases:
      - id: 147
        description: "Send connection-specific header field"
        connection_settings:
          client_side: true
          header_encoding: "utf-8"
          enable_push: false
          initial_window_size: 65535
        headers:
          pseudo_headers:
            method: "GET"
            scheme: "http"
            path: "/"
            authority: "localhost"
          regular_headers:
            connection: "keep-alive"
        frames:
          - type: "HEADERS"
            flags: ["END_STREAM"]
            stream_id: 1
```

## Test Suite

```yaml
name: string               # Name of the test suite
section: string           # Section reference in the specification
cases: array             # Array of test cases
```

## Test Case

```yaml
id: integer                  # Unique identifier for the test case
description: string          # Description of what the test case verifies
connection_settings: object
headers: object
frames: array
```

## Connection Settings

```yaml
connection_settings:
  client_side: boolean           # Whether this is client-side (default: true)
  header_encoding: string        # Header encoding (default: "utf-8")
  enable_push: boolean          # Enable server push (default: false)
  initial_window_size: integer  # Initial flow control window size
  max_frame_size: integer      # Maximum frame size
  max_header_list_size: integer # Maximum header list size
  settings: object            # Custom settings key-value pairs
```

### Settings

```yaml
settings:
  # Standard HTTP/2 Settings Parameters
  SETTINGS_HEADER_TABLE_SIZE: 4096      # Maximum size of header compression table
  SETTINGS_ENABLE_PUSH: 0               # 0 to disable server push, 1 to enable
  SETTINGS_MAX_CONCURRENT_STREAMS: 100   # Maximum concurrent streams allowed
  SETTINGS_INITIAL_WINDOW_SIZE: 65535   # Initial flow control window size
  SETTINGS_MAX_FRAME_SIZE: 16384        # Maximum size of a frame payload
  SETTINGS_MAX_HEADER_LIST_SIZE: 16384  # Maximum size of header list
  
  # Non-standard or custom settings (for testing)
  SETTINGS_UNKNOWN: 12345               # Unknown setting for error testing
  0x0f: 1                              # Custom setting identifier
```

## Headers

```yaml
headers:
  pseudo_headers:
    method: string          # :method pseudo-header
    scheme: string         # :scheme pseudo-header
    path: string          # :path pseudo-header
    authority: string     # :authority pseudo-header
    status: string       # :status pseudo-header (response only)
  regular_headers:
    name: string         # Regular header field name-value pairs
  duplicate_pseudo_headers:
    name: string        # Duplicate pseudo-headers for testing
```

## Frames

```yaml
frames:
  - type: string         # Frame type (HEADERS, SETTINGS, etc.)
    flags: array        # Array of flags for the frame
    stream_id: integer # Stream identifier
    settings: object  # Settings for SETTINGS frames
    padding: integer # Padding length for applicable frames
```

### Frame Types

```yaml
type:
  - "HEADERS"           # Headers frame
  - "SETTINGS"         # Settings frame
  - "DATA"             # Data frame
  - "PRIORITY"         # Priority frame
  - "RST_STREAM"       # Reset stream frame
  - "PUSH_PROMISE"     # Push promise frame
  - "PING"             # Ping frame
  - "GOAWAY"           # Go away frame
  - "WINDOW_UPDATE"    # Window update frame
  - "CONTINUATION"     # Continuation frame
```

### Frame Flags

```yaml
flags:
  - "END_STREAM"       # Ends the stream
  - "END_HEADERS"      # Ends the headers
  - "PADDED"           # Frame is padded
  - "PRIORITY"         # Priority information present
  - "ACK"              # Acknowledgment (for SETTINGS/PING)
```