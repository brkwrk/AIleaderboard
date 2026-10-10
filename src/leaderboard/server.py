"""Leaderboard Web Server - Simple website to create and view leaderboards.

Copyright (C) 2026  CoolCat467

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

__title__ = "Character Simulator Webserver"
__author__ = "CoolCat467"
__version__ = "0.1.0"
__license__ = "GNU General Public License Version 3"


import argparse
import sys
import traceback
from collections.abc import (
    AsyncIterator,
    Iterable,
)
from dataclasses import dataclass, field
from functools import partial
from os import getenv, makedirs, path
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Generic,
    TypedDict,
    TypeVar,
)
from uuid import UUID, uuid4

import httpx2 as httpx
import platformdirs
import trio
from dotenv import load_dotenv
from hypercorn.config import Config
from hypercorn.trio import serve
from quart import Response, request
from quart.templating import stream_template
from quart_trio import QuartTrio

from leaderboard.elapsed import combine_end
from leaderboard.llm_request import yield_llm_stream
from leaderboard.server_utils import (
    find_ip,
    get_exception_page,
    pretty_exception,
)

if sys.version_info < (3, 11):
    import tomli as tomllib
    from exceptiongroup import BaseExceptionGroup
else:
    import tomllib

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Coroutine
    from contextlib import AbstractAsyncContextManager

    from typing_extensions import ParamSpec
    from werkzeug import Response as WerkzeugResponse

    PS = ParamSpec("PS")

FILE_TITLE: Final = __title__.lower().replace(" ", "-").replace("-", "_")
CONFIG_PATH: Final = trio.Path(
    platformdirs.user_config_path(FILE_TITLE, __author__),
)
DATA_PATH: Final = trio.Path(
    platformdirs.user_data_path(FILE_TITLE, __author__),
)
MAIN_CONFIG: Final = CONFIG_PATH / "config.toml"

T = TypeVar("T")


@dataclass
class StreamConsumer(Generic[T]):
    """Stream consumer."""

    recv_chan: trio.MemoryReceiveChannel[T | None]
    lock: trio.Lock = field(default_factory=trio.Lock)

    @property
    def claimed(self) -> bool:
        """Return if this stream is claimed."""
        return self.lock.locked()

    @trio.as_safe_channel
    async def yield_response(self) -> AsyncGenerator[T, None]:
        """Yield response values until None is returned."""
        if self.lock.locked():
            raise OSError("Another task has already claimed this request.")
        # print("[yield_response] starting")
        async with self.lock:
            # print("[yield_response] got recv lock")
            async with self.recv_chan:
                while True:
                    value = await self.recv_chan.receive()
                    if value is None:
                        break
                    yield value
        # print("[yield_response] completing")


# TODO: Switch back to `NamedTuple` after we drop 3.10 support.
@dataclass
class BackgroundStreamRequestPool(Generic[T]):
    """Background streaming request pool."""

    requests: dict[UUID, StreamConsumer[T]]
    nursery: trio.Nursery | None

    async def execute_request(
        self,
        ctx_manager: AbstractAsyncContextManager[trio.abc.ReceiveChannel[T]],
        task_status: trio.TaskStatus[UUID] = trio.TASK_STATUS_IGNORED,
    ) -> None:
        """Start executing request stream and send it to the receive channel."""
        send_chan, recv_chan = trio.open_memory_channel[T | None](0)

        uuid = uuid4()
        self.requests[uuid] = StreamConsumer(recv_chan)

        task_status.started(uuid)

        # print("[execute_request] starting")
        try:
            async with send_chan:
                async with ctx_manager as gen_recv_chan:
                    async for fragment in gen_recv_chan:
                        await send_chan.send(fragment)
                await send_chan.send(None)
        except trio.BrokenResourceError:
            # client closed before llm was done
            pass
        finally:
            # print("[execute_request] completing")
            del self.requests[uuid]

    async def new_request(
        self,
        ctx_manager: AbstractAsyncContextManager[trio.abc.ReceiveChannel[T]],
    ) -> UUID:
        """Return new UUID associated with streaming this request."""
        if self.nursery is None:
            raise RuntimeError(
                "nursery should have initialized with serve start",
            )
        result = await self.nursery.start(self.execute_request, ctx_manager)
        assert isinstance(result, UUID)
        return result

    def obtain_request(self, uuid: UUID) -> StreamConsumer[T] | None:
        """Return the associated stream consumer from a given UUID."""
        return self.requests.get(uuid)


class AppData(TypedDict):
    """Global shared application data."""

    client: httpx.AsyncClient
    key: str
    request_pool: BackgroundStreamRequestPool[str]


app: Final = QuartTrio(  # pylint: disable=invalid-name
    __name__,
    static_folder="static",
    template_folder="templates",
)
APP_DATA = AppData(
    {
        "client": httpx.AsyncClient(),
        "key": "fake key",
        "request_pool": BackgroundStreamRequestPool({}, None),
    },
)


@app.get("/")
async def root_get() -> AsyncIterator[str]:
    """Handle main page GET request."""
    return await stream_template(
        "character_simulator.html.jinja",
    )


def format_prompt(character_card: str, current_situation: str) -> str:
    """Return prompt for LLM given user input."""
    return f"""You are simulating how a character would act in a given situation as a writing assistance tool. Your response will be displayed as-is.
<character description>
{character_card}
</character description>
<situation>
{current_situation}
</situation>
"""


@app.post("/")
@pretty_exception
async def root_post() -> (
    WerkzeugResponse | AsyncIterator[str] | tuple[AsyncIterator[str], int]
):
    """Handle page POST."""
    multi_dict = await request.form
    form = multi_dict.to_dict()

    character_card = form.get("character_card", "").strip()
    current_situation = form.get("current_situation", "").strip()
    js_disabled = bool(form.get("js_disabled", ""))

    errors = []
    if not character_card:
        errors.append("Missing <code>character_card</code> parameter.")
    if not current_situation:
        errors.append("Missing <code>current_situation</code> parameter.")
    if errors:
        return await get_exception_page(
            400,  # bad request
            "Bad Request",
            "\n<br>\n".join(errors),
            request.url,
        )

    assert character_card
    assert current_situation

    prompt = format_prompt(character_card, current_situation)
    client = APP_DATA["client"]
    key = APP_DATA["key"]

    request_pool = APP_DATA["request_pool"]
    uuid = await request_pool.new_request(
        yield_llm_stream(prompt, client, key),
    )

    if js_disabled:
        # load directly since client can't
        stream = request_pool.obtain_request(uuid)
        if stream is None:
            return await get_exception_page(
                500,  # internal server error
                "Internal Server Error",
                "Somehow response stream is already claimed. Shouldn't be possible.",
                request.url,
            )

        async with stream.yield_response() as recv_chan:
            fragments = []
            async for fragment in recv_chan:
                fragments.append(fragment)

        return await stream_template(
            "character_simulator.html.jinja",
            character_card_autofill=character_card,
            current_situation_autofill=current_situation,
            response="".join(fragments),
        )

    # Javascript will take the uuid and load content from
    # /character_response dynamically on page load.
    return await stream_template(
        "character_simulator.html.jinja",
        character_card_autofill=character_card,
        current_situation_autofill=current_situation,
        response=str(uuid),
    )


@app.get("/character_response/<uuid:response_uuid>")
@pretty_exception
async def character_response_get(
    response_uuid: UUID,
) -> Response | tuple[str, int]:
    """Character response page get handling."""
    request_pool = APP_DATA["request_pool"]
    stream = request_pool.obtain_request(response_uuid)
    if stream is None:
        # page expired
        return "Requested page is expired or invalid.", 410

    async def generate() -> AsyncGenerator[bytes, None]:
        """Yield text fragments for javascript to load dynamically."""
        async with stream.yield_response() as recv_chan:
            async for fragment in recv_chan:
                yield fragment.encode("utf-8")

    return Response(generate(), content_type="text/plain; charset=utf-8")


async def async_run_server(
    serve_partial: partial[Coroutine[Any, Any, None]],
) -> None:
    """Call server partial while managing httpx client."""
    async with httpx.AsyncClient() as client:
        APP_DATA["client"] = client
        async with trio.open_nursery() as nursery:
            APP_DATA["request_pool"] = BackgroundStreamRequestPool({}, nursery)
            nursery.start_soon(serve_partial)


def run_server(
    secure_bind_port: int | None = None,
    insecure_bind_port: int | None = None,
    ip_addr: str | None = None,
    hypercorn: dict[str, object] | None = None,
) -> None:
    """Asynchronous Entry Point."""
    if secure_bind_port is None and insecure_bind_port is None:
        raise ValueError(
            "Port must be specified with `port` and or `ssl_port`!",
        )

    if not ip_addr:
        ip_addr = find_ip()

    if not hypercorn:
        hypercorn = {}

    ##    logs_path = platformdirs.user_log_path(FILE_TITLE, __author__)
    ##    if not path.exists(logs_path):
    ##        makedirs(logs_path)

    ##    print(f"Logs Path: {str(logs_path)!r}\n")

    try:
        # Hypercorn config setup
        config: dict[str, object] = {
            "accesslog": "-",
            ##"errorlog": logs_path / time.strftime("log_%Y_%m_%d.log"),
        }
        # Load things from user controlled toml file for hypercorn
        config.update(hypercorn)
        # Override a few particularly important details if set by user
        config.update(
            {
                "worker_class": "trio",
            },
        )
        # Make sure address is in bind

        if insecure_bind_port is not None:
            raw_bound = config.get("insecure_bind", [])
            if not isinstance(raw_bound, Iterable):
                raise ValueError(
                    "main.bind must be an iterable object (set in config file)!",
                )
            bound = set(raw_bound)
            bound |= {f"{ip_addr}:{insecure_bind_port}"}
            config["insecure_bind"] = bound

            # If no secure port, use bind instead
            if secure_bind_port is None:
                config["bind"] = config["insecure_bind"]
                config["insecure_bind"] = []

            insecure_locations = combine_end(
                f"http://{addr}" for addr in sorted(bound)
            )
            print(f"Serving on {insecure_locations} insecurely")

        if secure_bind_port is not None:
            raw_bound = config.get("bind", [])
            if not isinstance(raw_bound, Iterable):
                raise ValueError(
                    "main.bind must be an iterable object (set in config file)!",
                )
            bound = set(raw_bound)
            bound |= {f"{ip_addr}:{secure_bind_port}"}
            config["bind"] = bound

            secure_locations = combine_end(
                f"https://{addr}" for addr in sorted(bound)
            )
            print(f"Serving on {secure_locations} securely")

        app.config["EXPLAIN_TEMPLATE_LOADING"] = False

        # We want pretty html, no jank
        app.jinja_options = {
            "trim_blocks": True,
            "lstrip_blocks": True,
        }

        app.add_url_rule("/<path:filename>", "static", app.send_static_file)

        config_obj = Config.from_mapping(config)

        print("(CTRL + C to quit)")

        trio.run(async_run_server, partial(serve, app, config_obj))
    except BaseExceptionGroup as exc:
        caught = False
        for ex in exc.exceptions:
            if isinstance(ex, KeyboardInterrupt):
                print("Shutting down from keyboard interrupt")
                caught = True
                break
        if not caught:
            traceback.print_exception(exc)
            raise


DEFAULT_CONFIG_TOML: Final = """[main]
# Port server should run on.
# You might want to consider changing this to 80
port = 3004

# Port for SSL secured server to run on
#ssl_port = 443

# Helpful stack exchange website question on how to allow non root processes
# to bind to lower numbered ports
# https://superuser.com/questions/710253/allow-non-root-process-to-bind-to-port-80-and-443
# Answer I used: https://superuser.com/a/1482188/1879931

[hypercorn]
# See https://hypercorn.readthedocs.io/en/latest/how_to_guides/configuring.html#configuration-options
use_reloader = false
# SSL configuration details
#certfile = "/home/<your_username>/letsencrypt/config/live/<your_domain_name>.duckdns.org/fullchain.pem"
#keyfile = "/home/<your_username>/letsencrypt/config/live/<your_domain_name>.duckdns.org/privkey.pem"
"""


def run() -> None:
    """Run scanner server."""
    parser = argparse.ArgumentParser(
        description="Simple website to create and view leaderboards. ",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{__title__} v{__version__}",
        help="Show the program version and exit.",
    )
    parser.add_argument(
        "--create-default-config",
        action="store_true",
        help="Create or overwrite the default configuration file.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Bind to localhost (127.0.0.1) instead of public ip address.",
    )

    args = parser.parse_args()

    if args.create_default_config:
        print(
            f"Creating/overwriting configuration file located at {str(MAIN_CONFIG)!r} with default...",
        )
        if not path.exists(CONFIG_PATH):
            makedirs(CONFIG_PATH)

        with open(MAIN_CONFIG, "w", encoding="utf-8") as fp:
            fp.write(DEFAULT_CONFIG_TOML)

        print("Action complete.")
        return

    if path.exists(MAIN_CONFIG):
        print(f"Reading configuration file {str(MAIN_CONFIG)!r}...\n")

        with open(MAIN_CONFIG, "rb") as fp:
            config = tomllib.load(fp)
    else:
        print(
            f"Configuration file {str(MAIN_CONFIG)!r} not found, loading default.",
        )
        config = tomllib.loads(DEFAULT_CONFIG_TOML)

    main_section = config.get("main", {})

    insecure_bind_port = main_section.get("port", None)
    secure_bind_port = main_section.get("ssl_port", None)

    hypercorn: dict[str, object] = config.get("hypercorn", {})

    ip_address: str | None = None
    if args.local:
        ip_address = "127.0.0.1"

    load_dotenv()

    key = getenv("OPENROUTER_KEY")
    if key is None:
        raise KeyError("`OPENROUTER_KEY` not found in environment")
    APP_DATA["key"] = key

    run_server(
        secure_bind_port=secure_bind_port,
        insecure_bind_port=insecure_bind_port,
        ip_addr=ip_address,
        hypercorn=hypercorn,
    )


if __name__ == "__main__":
    run()
