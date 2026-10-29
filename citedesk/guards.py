"""Limits on what the API will take in: how big a request body may be, and how fast inquiries may
arrive (docs/TRD.md section 8, Phase 8).

Neither limit looks at message text. They exist so that a runaway script or a mistaken upload cannot
fill the machine's memory or the queue.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyTooLarge(StarletteHTTPException):
    """The request body went over its limit: an HTTP 413, answered in the API's error shape."""

    def __init__(self) -> None:
        super().__init__(status_code=413)


class BodyLimit:
    """Refuse a request body that is bigger than its limit, before the app has read all of it.

    A body that declares its size in `Content-Length` is refused on the first read without being
    received. One that does not (chunked), or that lies, is counted as it arrives and refused the
    moment it goes over. `limit_for` gives the limit for a request path.
    """

    def __init__(self, app: ASGIApp, *, limit_for: Callable[[str], int]) -> None:
        self.app = app
        self.limit_for = limit_for

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope["path"])
        declared = self._declared_length(scope)
        seen = 0

        async def guarded() -> Message:
            nonlocal seen
            if declared is not None and declared > limit:
                raise BodyTooLarge()
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise BodyTooLarge()
            return message

        await self.app(scope, guarded, send)

    @staticmethod
    def _declared_length(scope: Scope) -> int | None:
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None


class RateLimiter:
    """At most `per_minute` requests in any 60 seconds, counted over a sliding window.

    One window for the whole app, because v1 serves one person on one machine. `per_minute` of 0
    turns the limit off. `check` returns None if the request may go ahead, or how many seconds to
    wait before it could.
    """

    WINDOW_SECONDS = 60.0

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_minute = per_minute
        self._clock = clock
        self._times: deque[float] = deque()
        self._lock = threading.Lock()

    def check(self) -> int | None:
        if self.per_minute <= 0:
            return None
        with self._lock:
            now = self._clock()
            while self._times and now - self._times[0] >= self.WINDOW_SECONDS:
                self._times.popleft()
            if len(self._times) >= self.per_minute:
                return max(1, math.ceil(self.WINDOW_SECONDS - (now - self._times[0])))
            self._times.append(now)
            return None


def max_json_bytes(max_body_chars: int) -> int:
    """The most a JSON request may weigh: a message at its character limit with every character
    escaped (6 bytes each), plus room for the other fields."""
    return max_body_chars * 6 + 64 * 1024
