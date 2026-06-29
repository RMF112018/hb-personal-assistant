# DCR Samples

Request:

```json
{"redirect_uris":["https://chatgpt.com/connector/oauth/runtime-proof"],"grant_types":["authorization_code"],"response_types":["code"],"token_endpoint_auth_method":"none","scope":"obsidian.read","client_name":"ChatGPT Runtime Proof"}
```

Response:

```json
{"client_id":"chatgpt_<redacted>","redirect_uris":["https://chatgpt.com/connector/oauth/runtime-proof"],"grant_types":["authorization_code"],"response_types":["code"],"token_endpoint_auth_method":"none","scope":"obsidian.read","client_name":"ChatGPT Runtime Proof","client_id_issued_at":1782717478}
```

