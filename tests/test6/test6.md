Scenario: Sending an Invalid Dynamic Table Size Update

According to RFC 7541 (HPACK), the dynamic table size update must always be less than or equal to the maximum size set by the SETTINGS_HEADER_TABLE_SIZE parameter. Sending an update that exceeds the allowed maximum size will make the packet non-conformant.