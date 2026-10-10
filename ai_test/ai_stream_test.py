"""LLM Response Test.

PLEASE READ! (or don't, I'm not your mom.)

This is a simple script that leverages OpenRouter's API to communicate
with a generative AI model to get a response. Currently, this is only
designed with text -> text in mind, but I'm sure it can be expanded to
get other kinds of responses should we so need.

To use this script, you'll need to add an OpenRouter API key to a .env
file (example provided to be used as a template). I'll try to get you
guys the key I'm using, which is set up for free models from OpenRouter.
If a paid one is used accidentally, the key will max out at $1 worth of
credits. When using free models with my key, you shouldn't have to worry
about running into any daily limits (just don't get too wild with the
prompting).

Anyways, below is a function that can be used to get a text response
from a model based on some prompt, and a main function to test this in
the console is provided. You can try it out by just running this file
and entering some prompt. Feel free to change the AI model used to
something else.

Below are a few links that could be useful in using this API...
OpenRouter models list (search "free" for other free models):
https://openrouter.ai/models OpenRouter API documentation:
https://openrouter.ai/docs/api_reference/overview

Hopefully, this is a solid foundation for creating the backend of this
application. If this API sucks, we can always find a different one, but
I've used OpenRouter a bit before so I figured I would try it first. Let
me know if nothing of what I just said makes any sense.

- Luke (johnsonl651@lopers.unk.edu)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import httpx2 as httpx
import orjson
import trio
from dotenv import load_dotenv

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

load_dotenv()


async def yield_llm_stream(
    prompt: str,
    client: httpx.AsyncClient,
    key: str,
    model: str = "dots-studio/dots-3-note-preview:free",
) -> AsyncGenerator[str, None]:
    """Yield a stream of text fragments from LLM provider request."""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }

    async with client.stream(
        "POST",
        url="https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        data=orjson.dumps(payload),
        timeout=50,
    ) as response:
        # check pre-stream errors
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as http_exc:
            try:
                error_data = orjson.loads(await response.aread())
            except orjson.JSONDecodeError as decode_exc:
                # raise decode error from http error
                raise decode_exc from http_exc
            # if the API returned an error, add error message as a note
            http_exc.add_note(error_data["error"]["message"])
            raise http_exc from None

        async for line in response.aiter_lines():
            # Skip blank lines and SSE comments (for example, keep-alive
            # messages).
            if not line or line.startswith(":"):
                continue

            if not line.startswith("data: "):
                continue

            data = line[6:]
            if data == "[DONE]":
                break

            try:
                parsed = orjson.loads(data)
            except orjson.JSONDecodeError:
                continue

            # Check for mid-stream error
            if "error" in parsed:
                raise OSError(parsed["error"]["message"])

            content = parsed["choices"][0]["delta"].get("content")
            if content:
                yield content


async def async_main() -> None:
    """Asynchronous entry point."""
    key = os.getenv("OPENROUTER_KEY")

    if key is None:
        raise RuntimeError("`OPENROUTER_KEY` not found in environment.")

    # get input from console and display the response (or an error if
    # something goes wrong)
    prompt = await trio.to_thread.run_sync(input, "Enter prompt: ")

    async with httpx.AsyncClient() as client:
        print("<start LLM response text>")
        async for fragment in yield_llm_stream(prompt, client, key=key):
            print(fragment, end="", flush=True)
        print()
        print("<stop LLM response text>")


def main() -> None:
    """Run program."""
    trio.run(async_main)


if __name__ == "__main__":
    main()
