Scenario: Client Sending a Request with an Even-Numbered Stream Identifier

According to RFC 7540, clients MUST use odd-numbered stream identifiers when initiating new streams. Sending a request with an even-numbered stream identifier would violate this rule and make the packet non-conformant.