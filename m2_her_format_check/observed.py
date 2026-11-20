"""Values observed on the official M2-her endpoint that the cases depend on.

Recorded on 2026-11-05 from repeated full runs against the official MiniMax
native endpoint (/v1/text/chatcompletion_v2, model M2-her). Invalid requests
are not pinned to an error code or message: they only need to fail (see
helpers.assert_request_failed), so providers may report errors their own way.
"""

# n=1..4 return n candidates on the official endpoint; n=5 fails.
# --n-limit replaces this value for a deployment with another documented limit.
N_LIMIT = 4
