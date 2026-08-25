# Test fixtures

Place sanitized OneBot v11 payloads in this directory. Remove bot IDs, user IDs,
group IDs, tokens, cookies, private messages, and durable image URLs before commit.
Fixtures must never contact or depend on the live Yurisaki service.

Files whose names end in `_synthetic.json` are invented protocol-shaped examples,
not captured service responses. Real compatibility is verified separately with the
isolated checklist in `docs/REAL_INTEGRATION.md`. Never replace these files with raw
logs; only add a real fixture after it has been strictly sanitized.

`yurisaki_rand_response.json` records the stable shape observed in three real
`/a rand` responses on 2026-08-25: one event containing image then text, with
account IDs, message IDs, timestamps, image identifiers, sizes, and URLs replaced.
