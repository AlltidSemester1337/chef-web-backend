"""Welcome to Reflex! This file outlines the steps to create a basic app."""
import os

import firebase_admin
import reflex as rx

from chef_web import style
from chef_web.state import State

FIREBASE_URL = os.getenv("FIREBASE_URL")


def navbar_link(text: str, url: str) -> rx.Component:
    return rx.link(
        rx.text(text, size="4", weight="medium"), href=url
    )


def navbar() -> rx.Component:
    return rx.box(
        rx.desktop_only(
            rx.hstack(
                rx.hstack(
                    logo(),
                    rx.heading(
                        "Chef", size="7", weight="bold"
                    ),
                    rx.cond(State.user, rx.text("Logged in as: " + State.user.email), rx.text("")),
                    align_items="center",
                ),
                rx.hstack(
                    navbar_link("Generate new recipes!", "/"),
                    navbar_link("View favourites", "/recipes"),
                    rx.cond(State.user, rx.button("Log out", on_click=State.logout),
                            rx.button("Log in", on_click=rx.redirect("/login"))),
                    justify="end",
                    spacing="5",
                ),
                justify="between",
                align_items="center",
            ),
        ),
        rx.mobile_and_tablet(
            rx.hstack(
                rx.hstack(
                    # rx.image(
                    # src="/res/logo.jpg",
                    # width="2em",
                    # height="auto",
                    # border_radius="25%",
                    # ),
                    rx.heading(
                        "Chef", size="6", weight="bold"
                    ),
                    align_items="center",
                ),
                rx.menu.root(
                    rx.menu.trigger(
                        rx.icon("menu", size=30)
                    ),
                    rx.menu.content(
                        rx.menu.item("Generate new recipes!"),
                        rx.menu.item("View favourites"),
                    ),
                    justify="end",
                ),
                justify="between",
                align_items="center",
            ),
        ),
        bg=rx.color("accent", 3),
        padding="0.5em",
        width="100%",
        position="fixed",
        top="0",
        z_index="1000",
    )


def logo():
    return rx.image(
        src="/chef-web/logo.jpg",
        width="2.25em",
        height="auto",
        border_radius="25%",
    )


def qa(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(
            rx.text(question, style=style.question_style),
            text_align="left",
        ),
        rx.box(
            rx.text(answer),
            rx.flex(rx.icon(
                "star",
                on_click=State.add_to_favourites(answer),
                color_scheme="gray",
                color=rx.cond(
                    State.answers_in_favourites[answer], "yellow", "gray"
                ),
                justify="end",
                align="end",
                width="100%"
            ),
                width="100%",
                text_align="right",
            ),
            style=style.answer_style,
            margin_y="1em",
            width="100%",
        )
    )


def chat() -> rx.Component:
    return rx.box(
        rx.foreach(
            State.chat_history,
            lambda messages: qa(messages[0], messages[1]),
        ),
        rx.script("setTimeout(() => {window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })}, 1000)"),
        margin_y="2em"
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
    return rx.box(navbar(),
                  rx.center(
                      rx.vstack(
                          chat(),
                          action_bar(),
                          align="center",
                      )
                  ))


def recipe() -> rx.Component:
    return rx.box(navbar(),
                  rx.center(
                      rx.vstack(
                          recipe_detail(),
                          align="center",
                      )
                  ))


def recipe_detail() -> rx.Component:
    return rx.box(
        rx.cond(
            State.selected_recipe != None,  # If a recipe is loaded...
            rx.box(
                # Display the recipe title.
                rx.center(rx.text(State.selected_recipe.title, style=style.title_style)),
                # If there's an image URL, display the image.
                rx.cond(
                    State.selected_recipe.image_url != None,
                    rx.center(rx.image(State.selected_recipe.image_url, align="center")),
                    rx.box()
                ),
                rx.html("<br>"),
                # Display the summary.
                rx.center(format_text(text=State.selected_recipe.summary, text_style=style.summary_style)),
                rx.html("<br>"),
                # Toggle buttons for ingredients and instructions.
                rx.hstack(
                    rx.button(
                        "Ingredients",
                        on_click=State.toggle_view,
                        width="100px"
                    ),
                    rx.button(
                        "Instructions",
                        on_click=State.toggle_view,
                        width="100px"
                    ),
                    justify="center",
                    align="center",
                    width="100%"
                ),
                rx.html("<br>"),
                # Conditionally display ingredients or instructions.
                rx.cond(
                    State.show_ingredients,
                    format_text(text=State.selected_recipe.ingredients),
                    format_text(text=State.selected_recipe.instructions)
                ),
                padding="1em"
            ),
            # Else: if no recipe is found
            rx.text("No recipe with matching ID found. Make sure to include id=<recipe_id> in the URL.")
        ),
        width="100%"
    )


# TODO This is not really the right place to solve this, perhaps rethink line break handling. Await Bobo design anyway
def format_text(text: str, text_style: style = style.detail_text_style) -> rx.Component:
    """Splits text by newlines and returns an rx.box with individual text components."""
    return rx.box(
        rx.foreach(
            text.split("\\n"),
            lambda line: rx.cond(line.strip() == "",  # If line is empty
                                 rx.box()
                                 ,
                                 rx.box(
                                     rx.text(line, style=text_style),
                                     rx.html("<br>"),
                                 )
                                 )
        ),
        align="start"
    )


def recipes() -> rx.Component:
    return rx.box(navbar(),
                  rx.center(rx.box(
                      rx.text("Favourite recipes", style=style.title_style),
                      rx.cond(State.favourites_recipes_list,

                              rx.vstack(
                                  rx.foreach(
                                      State.favourites_recipes_list,
                                      lambda fav_recipe: recipe_list_item(fav_recipe.id, fav_recipe.title),
                                  ),
                                  align="center",
                                  width="100%",  # Ensure full width for centering
                                  spacing="1",  # Add spacing between items
                              )
                              ,
                              rx.text("No recipes found, go create and star some!"))
                  )))


def recipe_list_item(id: str, title: str) -> rx.Component:
    return rx.box(
        rx.text(title, style=style.summary_style),
        on_click=State.redirect_to_recipe(id),
        style=style.answer_style,
    )


def login() -> rx.Component:
    return rx.box(rx.cond(
        State.redirect_to,  # If redirect URL is set
        rx.script(f"window.location.href = '{State.redirect_to}';"),  # Perform client-side redirect
        rx.box(navbar(), rx.center(rx.card(
            rx.vstack(
                rx.center(
                    logo(),
                    rx.heading(
                        "Sign in to your Chef account",
                        size="6",
                        as_="h2",
                        text_align="center",
                        width="100%",
                    ),
                    direction="column",
                    spacing="5",
                    width="100%",
                ),
                rx.vstack(
                    rx.text(
                        "Email address",
                        size="3",
                        weight="medium",
                        text_align="left",
                        width="100%",
                    ),
                    rx.input(
                        placeholder="email@email.com",
                        on_blur=State.set_user_email,
                        type="email",
                        size="3",
                        width="100%",
                    ),
                    justify="start",
                    spacing="2",
                    width="100%",
                ),
                rx.button("Sign in / Register", on_click=State.login_sign_up, size="3", width="100%"),
                spacing="6",
                width="100%",
            ),
            size="4",
            max_width="28em",
            width="100%",
        )
        ), height="100vh",  # Full viewport height
               display="flex",
               align_items="center",  # Vertical centering
               justify_content="center",  # Horizontal centering
               )
    ))


firebase_admin.initialize_app(options={
    "databaseURL": FIREBASE_URL
})

app = rx.App()
app.add_page(index, on_load=State.check_user_permissions)
app.add_page(recipe, on_load=State.load_recipe)
app.add_page(recipes, on_load=State.load_recipes_list)
app.add_page(login)
