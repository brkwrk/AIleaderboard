#!/usr/bin/env python3

"""Generate pages for the leaderboard web server.

Copyright (C) 2022-2026  CoolCat467

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

__title__ = "Generate Pages"
__author__ = "CoolCat467"
__license__ = "GNU General Public License Version 3"


import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from leaderboard import htmlgen, server

if TYPE_CHECKING:
    from collections.abc import Callable

MODULE: Final = Path(__file__).absolute().parent
SOURCE_ROOT: Final = MODULE.parent.parent

TEMPLATE_FOLDER: Final = MODULE / "templates"
TEMPLATE_FUNCTIONS: dict[Path, Callable[[], str]] = {}
STATIC_FOLDER: Final = MODULE / "static"
STATIC_FUNCTIONS: dict[Path, Callable[[], str]] = {}


def save_content(path: Path, content: str) -> None:
    """Save content to given path."""
    path.write_text(content + "\n", encoding="utf-8")
    print(f"Saved content to {path}")


def save_template_as(
    filename: str,
) -> Callable[[Callable[[], str]], Callable[[], str]]:
    """Save generated template as filename."""
    path = TEMPLATE_FOLDER / f"{filename}.html.jinja"

    def function_wrapper(function: Callable[[], str]) -> Callable[[], str]:
        if path in TEMPLATE_FUNCTIONS:
            raise NameError(
                f"{filename!r} already exists as template filename",
            )
        TEMPLATE_FUNCTIONS[path] = function
        return function

    return function_wrapper


def save_static_as(
    filename: str,
) -> Callable[[Callable[[], str]], Callable[[], str]]:
    """Save generated static file as filename."""
    path = STATIC_FOLDER / filename

    def function_wrapper(function: Callable[[], str]) -> Callable[[], str]:
        if path in STATIC_FUNCTIONS:
            raise NameError(f"{filename!r} already exists as static filename")
        STATIC_FUNCTIONS[path] = function
        return function

    return function_wrapper


@save_static_as("style.css")
def generate_style_css() -> str:
    """Generate style.css static file."""
    mono = "SFMono-Regular,SF Mono,Menlo,Consolas,Liberation Mono,monospace"
    return "\n".join(
        (
            htmlgen.css(
                ("*", "*::before", "*::after"),
                box_sizing="border-box",
                font_family="Lucida Console",
            ),
            htmlgen.css(("h1", "footer"), text_align="center"),
            htmlgen.css(("html", "body"), height="100%"),
            htmlgen.css(
                "body",
                line_height=1.5,
                _webkit_font_smoothing="antialiased",
                display="flex",
                flex_direction="column",
            ),
            htmlgen.css(".content", flex=(1, 0, "auto")),
            htmlgen.css(
                ".footer",
                flex_shrink=0,
            ),
            htmlgen.css(
                ("img", "picture", "video", "canvas", "svg"),
                display="block",
                max_width="100%",
            ),
            htmlgen.css(
                ("input", "button", "textarea", "select"),
                font="inherit",
            ),
            htmlgen.css(
                ("p", "h1", "h2", "h3", "h4", "h5", "h6"),
                overflow_wrap="break-word",
            ),
            htmlgen.css(
                ("#root", "#__next"),
                isolation="isolate",
            ),
            htmlgen.css(
                "code",
                padding=("0.2em", "0.4em"),
                background_color="rgba(158,167,179,0.4)",
                border_radius="6px",
                font_family=mono,
                line_height=1.5,
            ),
            htmlgen.css(
                "::placeholder",
                font_style="italic",
            ),
            htmlgen.css(
                ".box",
                background="ghostwhite",
                padding="0.5%",
                border_radius="4px",
                border=("2px", "solid", "black"),
                margin="0.5%",
                width="fit-content",
            ),
            htmlgen.css(
                "#noticeText",
                font_size="10px",
                display="inline-block",
                white_space="nowrap",
            ),
            htmlgen.css(
                'input[type="submit"]',
                border=("1.5px", "solid", "black"),
                border_radius="4px",
                padding="0.5rem",
                margin_left="0.5rem",
                margin_right="0.5rem",
                min_width="min-content",
            ),
            htmlgen.css(
                "@media (prefers-color-scheme: dark)",
                htmlgen.css(
                    "body",
                    background_color="#181818",
                    color="#e0e0e0",
                ),
                htmlgen.css(
                    ".box",
                    background_color="#1e1e1e",
                    border=("2px", "solid", "#444"),
                ),
                htmlgen.css(
                    "code",
                    background_color="rgba(255, 255, 255, 0.1)",
                ),
                htmlgen.css(
                    ("input", "button"),
                    background_color="#1e1e1e",
                    color="#e0e0e0",
                    border=("2px", "solid", "#444"),
                ),
                htmlgen.css(
                    ("input:hover", "button:hover"),
                    background_color="#4a4a4a",
                ),
            ),
        ),
    )


@save_template_as("base")
def base_template() -> str:
    """Generate base HTML Template for application."""
    head_data = "\n".join(
        (
            htmlgen.tag(
                "link",
                rel="stylesheet",
                type_="text/css",
                href="/style.css",
            ),
            htmlgen.jinja_block("head", scoped=True, block=False),
        ),
    )

    footer = f"{server.__title__} v{server.__version__} © {server.__author__}"

    body_data = "\n".join(
        (
            htmlgen.wrap_tag(
                "div",
                "\n".join(
                    (
                        htmlgen.wrap_tag(
                            "h1",
                            htmlgen.jinja_expression("self.title()"),
                            False,
                        ),
                        htmlgen.jinja_block(
                            "body",
                            scoped=True,
                            required=True,
                            block=False,
                        ),
                    ),
                ),
                class_="content",
            ),
            htmlgen.wrap_tag(
                "footer",
                "\n".join(
                    (
                        htmlgen.wrap_tag(
                            "i",
                            "If you're reading this, the web server was installed correctly.™",
                            block=False,
                        ),
                        htmlgen.tag("hr"),
                        htmlgen.wrap_tag(
                            "p",
                            footer,
                            block=False,
                        ),
                    ),
                ),
            ),
        ),
    )

    return htmlgen.template(
        htmlgen.jinja_block(
            "title",
            scoped=True,
            required=True,
            block=False,
        ),
        body_data,
        head=head_data,
        lang=htmlgen.jinja_block(
            "lang",
            "en",
            scoped=True,
            block=False,
        ),
    )


def template(
    title: str,
    body: str,
    *,
    head: str = "",
    lang: str = "en",
) -> str:
    """Use base HTML Template for application."""
    sections = [
        htmlgen.jinja_extends("base.html.jinja"),
        htmlgen.jinja_block("title", title, block=False),
    ]

    if head:
        sections.append(htmlgen.jinja_block("head", head))

    if lang != "en":
        sections.append(htmlgen.jinja_block("lang", lang))

    sections.append(htmlgen.jinja_block("body", body))

    return "\n".join(sections)


@save_template_as("error_page")
def generate_error_page() -> str:
    """Generate error response page."""
    error_text = htmlgen.wrap_tag("p", htmlgen.jinja_expression("error_body"))
    content = "\n".join(
        (
            error_text,
            htmlgen.tag("br"),
            htmlgen.jinja_if_block(
                {
                    "return_link": "\n".join(
                        (
                            htmlgen.create_link(
                                htmlgen.jinja_expression("return_link"),
                                "Return to previous page",
                            ),
                            htmlgen.tag("br"),
                        ),
                    ),
                },
            ),
            htmlgen.create_link("/", "Return to main page"),
        ),
    )
    body = htmlgen.contain_in_box(content)
    return template(
        htmlgen.jinja_expression("page_title"),
        body,
    )


@save_template_as("character_simulator")
def generate_character_simulator() -> str:
    """Generate / (root) GET/POST page."""
    character_card_min_rows = 8

    character_card_textarea = "\n<br>\n".join(
        (
            htmlgen.wrap_tag(
                "label",
                "Character Description",
                block=False,
                for_="character_card",
            ),
            htmlgen.jinja_with_block(
                htmlgen.wrap_tag(
                    "textarea",
                    htmlgen.jinja_expression("body|escape"),
                    block=False,
                    name="character_card",
                    id_="character_card",
                    rows=htmlgen.jinja_expression(
                        f"(body.count('\\n') + 1,{character_card_min_rows})|max",
                    ),
                    cols=80,
                    required=True,
                ),
                {
                    "body": "character_card_autofill|default('')|wordwrap",
                },
            ),
        ),
    )

    current_situation_min_rows = character_card_min_rows

    current_situation_textarea = "\n<br>\n".join(
        (
            htmlgen.wrap_tag(
                "label",
                "Current Situation",
                block=False,
                for_="current_situation",
            ),
            htmlgen.jinja_with_block(
                htmlgen.wrap_tag(
                    "textarea",
                    htmlgen.jinja_expression("body|escape"),
                    block=False,
                    name="current_situation",
                    id_="current_situation",
                    rows=htmlgen.jinja_expression(
                        f"(body.count('\\n') + 1,{current_situation_min_rows})|max",
                    ),
                    cols=80,
                    required=True,
                ),
                {
                    "body": "current_situation_autofill|default('')|wordwrap",
                },
            ),
        ),
    )

    no_javascript_element = htmlgen.wrap_tag(
        "noscript",
        htmlgen.input_field(
            "js_disabled",
            None,
            field_type="hidden",
            attrs={"value": 1},
        ),
    )

    form_contents = "\n<br>\n".join(  # noqa: FLY002
        (
            character_card_textarea,
            current_situation_textarea,
            no_javascript_element,
        ),
    )

    simulate_character_form = htmlgen.form(
        "simulate_character",
        form_contents,
        "Simulate",
        "Simulate a Character",
    )

    response = "\n<br>\n".join(
        (
            htmlgen.wrap_tag(
                "label",
                "LLM Response",
                block=False,
                for_="response",
            ),
            htmlgen.jinja_with_block(
                htmlgen.wrap_tag(
                    "textarea",
                    htmlgen.jinja_expression("body|escape"),
                    block=False,
                    name="response",
                    id_="response",
                    rows=htmlgen.jinja_expression("body.count('\\n') + 1"),
                    cols=80,
                    readonly=True,
                ),
                {
                    "body": "response|wordwrap",
                },
            ),
        ),
    )

    response_section = htmlgen.jinja_if_block(
        {
            "response": htmlgen.contain_in_box(response),
        },
    )

    html = "\n".join(
        (
            htmlgen.contain_in_box(simulate_character_form),
            response_section,
        ),
    )

    title_extra = htmlgen.jinja_if_block(
        {
            "response": " Response",
        },
        block=False,
    )

    return template(f"LLM Character Simulator{title_extra}", html)


def matches_disk_files(new_files: dict[Path, str]) -> bool:
    """Return if all new file contents match old file contents.

    Copied from src/trio/_tools/gen_exports.py, dual licensed under
    MIT and APACHE2.
    """
    for path, new_source in new_files.items():
        if not path.exists():
            return False
        # Strip trailing newline `save_content` adds.
        old_source = path.read_text(encoding="utf-8")[:-1]
        if old_source != new_source:
            return False
    return True


def process(do_test: bool) -> int:
    """Generate all page templates and static files. Return exit code."""
    new_files: dict[Path, str] = {}
    for filename, function in TEMPLATE_FUNCTIONS.items():
        new_files[filename] = function()
    for filename, function in STATIC_FUNCTIONS.items():
        new_files[filename] = function()

    matches_disk = matches_disk_files(new_files)

    if do_test:
        if not matches_disk:
            print("Generated sources are outdated. Please regenerate.")
            return 1
    elif not matches_disk:
        for path, new_source in new_files.items():
            save_content(path, new_source)
        print("\nRegenerated sources successfully.")
        # With pre-commit integration, show that we edited files.
        return 1
    print("Generated sources are up to date.")
    return 0


def run() -> int:
    """Regenerate all generated files."""
    parser = argparse.ArgumentParser(
        description="Generate static and template files",
    )
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="test if code is still up to date",
    )
    parsed_args = parser.parse_args()

    # Double-check we found the right directory
    assert (SOURCE_ROOT / "LICENSE").exists()

    return process(do_test=parsed_args.test)


if __name__ == "__main__":
    print(f"{__title__}\nProgrammed by {__author__}.\n")
    sys.exit(run())
