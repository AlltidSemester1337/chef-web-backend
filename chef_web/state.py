# state.py
import logging
import os
from typing import AsyncIterable

import reflex as rx
import vertexai
from vertexai.generative_models import GenerativeModel, ChatSession, GenerationResponse

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")


class State(rx.State):
    # The current question being asked.
    question: str

    # Keep track of the chat history as a list of (question, answer) tuples.
    chat_history: list[tuple[str, str]]

    def check_token(self, token):
        return token == ACCESS_TOKEN

    def on_page_load(self):
        try:
            token = self.router.page.full_raw_path.split("=")[1]
            if not self.check_token(token):
                return rx.redirect("/access_denied")
        except Exception as e:
            logging.warning(f"Error: {e}", exc_info=True)
            return rx.redirect("/access_denied")

    @rx.event
    async def answer(self):
        project_id = os.getenv("PROJECT_ID")
        location = "europe-west1"

        vertexai.init(
            project=project_id,
            location=location,
        )

        # System instruction for the AI model
        system_instruction = (
            "You are a personal chef / cooking assistant to help with coming up for new ideas on recipes. "
            "Use https://www.honestgreens.com/en/menu as inspiration for the whole foods, healthy, simple, and savory cooking/recipe style. "
            "Please use metric units and centiliters/deciliters for liquid measurements and state the nutritional values for each recipe."
        )

        # Generation parameters
        parameters = {
            "temperature": 2.0,
            "max_output_tokens": 8192,
            "top_p": 0.95,
        }

        model = GenerativeModel("gemini-1.5-flash-002", generation_config=parameters,
                                system_instruction=system_instruction)

        chat_session = model.start_chat()

        # Add to the answer as the chatbot responds.
        answer = ""
        self.chat_history.append((self.question, answer))

        session = self.stream_response(chat_session, self.question)
        # Clear the question input.
        self.question = ""
        # Yield here to clear the frontend input before continuing.
        yield

        async for chunk in session:
            answer += chunk.text
            self.chat_history[-1] = (
                self.chat_history[-1][0],
                answer,
            )
            yield

    async def stream_response(self, chat: ChatSession, question: str) -> AsyncIterable[GenerationResponse]:
        for chunk in chat.send_message(question, stream=True):
            yield chunk
