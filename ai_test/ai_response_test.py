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

import httpx2 as httpx
import orjson
import trio
from dotenv import load_dotenv

load_dotenv()


async def get_llm_response(
    prompt: str,
    client: httpx.AsyncClient,
    model: str = "dots-studio/dots-3-note-preview:free",
) -> str:
    """Retrieve a response from an AI model.

    This function takes in a prompt, sends it to an AI model using
    OpenRouter's API, and retrieves a response. This response is parsed
    to get just the actual message content from the model.

    Args:
        prompt: The string input sent to the model.
        model: The model used to get a response, set to a free model by
        default

    Returns:
         A string of the AI model's response to the prompt, or an error
         if the model cannot be connected to or a response cannot be
         found.

    """
    key = os.getenv("OPENROUTER_KEY")

    if not key:
        # if the API key can't be found, skip any attempt to get model
        # response
        return "ERROR: API key cannot be found."

    # send HTTP request to OpenRouter with a given prompt and model
    response = await client.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        data={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=50,
    )

    # get response as a dictionary
    try:
        text_reply = orjson.loads(await response.aread())
    except orjson.JSONDecodeError as decode_exc:
        # raise decode error from http error
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as http_exc:
            raise decode_exc from http_exc
        # if no http error re-raise json decode error
        raise

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # if the API returned an error, add error message as a note
        exc.add_note(text_reply["error"]["message"])
        raise exc

    # parse the model's response for the actual reply
    content = text_reply.get("choices")[0].get("message").get("content")
    if content:
        assert isinstance(content, str)
        return content

    # the final text response, set to an error message by default
    return "ERROR: Reply content could not be found."


async def async_main() -> None:
    """Asynchronous entry point."""
    async with httpx.AsyncClient() as client:
        # get input from console and display the response (or an error if
        # something goes wrong)
        prompt = await trio.to_thread.run_sync(input, "Enter prompt: ")
        result = await get_llm_response(prompt, client)
        print("<start LLM response text>")
        print(result)
        print("<stop LLM response text>")


def main() -> None:
    """Run program."""
    trio.run(async_main)


if __name__ == "__main__":
    main()
