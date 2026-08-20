# Test fixtures

Place sanitized OneBot v11 payloads in this directory. Remove bot IDs, user IDs,
group IDs, tokens, cookies, private messages, and durable image URLs before commit.
Fixtures must never contact or depend on the live Yurisaki service.

Files whose names end in `_synthetic.json` are invented protocol-shaped examples,
not captured service responses. They must be replaced or supplemented with sanitized
real fixtures before compatibility claims are made.
