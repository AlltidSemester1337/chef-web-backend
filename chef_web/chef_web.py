"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx
from chef_web import style
from chef_web.state import State


def qa(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(
            rx.text(question, style=style.question_style),
            text_align="left",
        ),
        rx.box(
            rx.text(answer, style=style.answer_style),
            text_align="right",
        ),
        margin_y="1em",
        width="100%",
    )


def chat() -> rx.Component:
    return rx.box(
        rx.foreach(
            State.chat_history,
            lambda messages: qa(messages[0], messages[1]),
        )
    )


def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=State.question,
            placeholder="Ask a question",
            on_change=State.set_question,
            style=style.input_style,
        ),
        rx.button(
            "Ask",
            on_click=State.answer,
            style=style.button_style,
        ),
    )


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            chat(),
            action_bar(),
            align="center",
        )
    )


@rx.page(route="/access_denied", title="Access Denied")
def access_denied() -> rx.Component:
    return rx.text("Invalid token")


app = rx.App()
app.add_page(index, on_load=State.on_page_load)
