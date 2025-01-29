# state.py
import logging
import os
from typing import AsyncIterable

import reflex as rx
import vertexai
from vertexai.generative_models import GenerativeModel, ChatSession, GenerationResponse
from firebase_admin import db
import json

CHAT_HISTORY_KEY = "chatHistory"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")


class State(rx.State):
    # The current question being asked.
    question: str

    # Keep track of the chat history as a list of (question, answer) tuples.
    chat_history: list[tuple[str, str]]

    # Function to fetch chat history from Firebase
    @staticmethod
    def load_history() -> list[tuple[str, str]]:
        ref = db.reference(CHAT_HISTORY_KEY)
        chat_data = ref.get()
        if chat_data:
            chat_history = list(chat_data.items())
            res = []
            # Format timestamps for display
            for i in range(0, len(chat_history), 2):
                question_value = chat_history[i][1]
                answer_value = chat_history[i + 1][1]
                if question_value and answer_value:
                    question = json.loads(question_value)["parts"][0]["text"]
                    answer = json.loads(answer_value)["parts"][0]["text"]
                    res += (question, answer),
            return res
        return []

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
        self.chat_history = self.load_history()

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
        original_question = self.question
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

        # Save to Firebase after the response is complete
        if original_question and answer:  # Ensure there's an question + answer to save
            ref = db.reference(CHAT_HISTORY_KEY)

            # TODO look further into tx issues, or how to deal with potential corruption?
            ref.push().set(json.dumps({
                "parts": [
                    {"text": original_question},
                ],
                "role": "user",
            }))
            ref.push().set(json.dumps({
                "parts": [
                    {"text": answer},
                ],
                "role": "model",
            }))

    async def stream_response(self, chat: ChatSession, question: str) -> AsyncIterable[GenerationResponse]:
        for chunk in chat.send_message(question, stream=True):
            yield chunk
