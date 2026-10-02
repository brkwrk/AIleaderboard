"""LLM Request - Perform a request to a large language model provider."""

# Programmed by CoolCat467

from __future__ import annotations

# LLM Request - Perform a request to a large language model provider
# Copyright (C) 2026  CoolCat467
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__title__ = "LLM Request"
__author__ = "CoolCat467"
__license__ = "GNU General Public License Version 3"

import os

import httpx2 as httpx
import orjson
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
        raise KeyError("OPENROUTER_KEY not found in environment")

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
        response_body = orjson.loads(await response.aread())
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
        exc.add_note(response_body["error"]["message"])
        raise exc

    # parse the model's response for the actual reply
    content = response_body.get("choices")[0].get("message").get("content")
    if content:
        assert isinstance(content, str)
        return content

    new_exc = ValueError("could not find message content in response body")
    new_exc.add_note(f"{response_body = }")
    raise new_exc
