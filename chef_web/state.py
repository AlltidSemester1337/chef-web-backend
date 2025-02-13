# state.py
import datetime
import logging
import os
import uuid
from typing import AsyncIterable

import reflex as rx
import vertexai
from vertexai.generative_models import GenerativeModel, ChatSession, GenerationResponse
from firebase_admin import db
import json
from google.cloud import storage

from vertexai.vision_models import ImageGenerationModel

from chef_web.model.recipe import Recipe

CHAT_HISTORY_KEY = "chatHistory"
FAVOURITES_KEY = "favourites"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")


class State(rx.State):
    # The current question being asked.
    question: str

    # Keep track of the chat history as a list of (question, answer) tuples.
    chat_history: list[tuple[str, str]]

    # TODO List of favourite recipes, should be updated to use recipes_list instead in future version
    favourites: list[str] = list()

    # state to track selected recipe on detail page
    selected_recipe: Recipe | None = None
    # Boolean to track which view to show on detail page.
    show_ingredients: bool = True

    # List of all favourite recipes
    favourites_recipes_list: list[Recipe]

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
        location = "europe-north1"

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

            try:
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
            except Exception as e:
                logging.error(f"Error saving chatHistory: {e}", exc_info=True)

    async def stream_response(self, chat: ChatSession, question: str) -> AsyncIterable[GenerationResponse]:
        for chunk in chat.send_message(question, stream=True):
            yield chunk

    @rx.event
    async def add_to_favourites(self, answer: str):
        # TODO else self.favourites.remove(answer)
        """Add the selected recipe to the Firebase 'favourites' table."""

        ref = db.reference(FAVOURITES_KEY)
        title, summary, ingredients, instructions = None, None, None, None
        try:
            title = self.derive_recipe_title(answer)
            summary = self.derive_recipe_summary(answer, title=title)
            ingredients = self.derive_recipe_ingredients(answer, title=title, summary=summary)
            instructions = self.derive_recipe_instructions(answer)
        except Exception as e:
            logging.warning(f"Error derive details from recipe: {e}", exc_info=True)
            return

        if not title and summary and ingredients and instructions:
            logging.warning(f"Failed to derive details from recipe: {answer}")
            return

        try:
            image_url = self.generate_image_for_recipe(answer)
        except Exception as e:
            logging.warning(f"Error generating image for recipe: {e}", exc_info=True)
            image_url = None

        updatedAt = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        # Create recipe data
        recipe_entry = {
            "title": title,
            "summary": summary,
            "ingredients": ingredients,
            "instructions": instructions,
            "imageUrl": image_url,
            "updatedAt": updatedAt,
        }

        try:
            # Push recipe entry to Firebase
            new_ref = ref.push()
            recipe_entry["id"] = new_ref.key
            new_ref.set(json.dumps(recipe_entry))
            # TODO Add a success message to the frontend? Or open detail window automatically? Consult with Bobo
            print("Recipe saved successfully!")  # Debugging
        except Exception as e:
            logging.error(f"Error saving recipe: {e}", exc_info=True)
        self.favourites.append(answer)

    def derive_recipe_title(self, answer: str) -> str | None:
        """Derive the recipe title from the chatbot response."""
        title = answer.split("\n\n")[0].replace("##  ", "")
        return title

    def derive_recipe_summary(self, answer: str, title: str) -> str | None:
        """Derive the recipe title from the chatbot response."""
        summary = answer.split("**Ingredients:**")[0].replace(title, "").replace("##  \n\n", "")
        return summary

    def derive_recipe_ingredients(self, answer: str, title: str, summary: str) -> str | None:
        """Derive the ingredients from the chatbot response."""
        # TODO Try to create list using \n? Maybe but think about benefits / downside on the collection recipe details page
        ingredients = answer.split("**Instructions:**")[0].replace(title, "").replace(summary, "").replace("##  \n\n",
                                                                                                           "")
        return ingredients

    def derive_recipe_instructions(self, answer: str) -> str | None:
        """Derive the instructions from the chatbot response."""
        # TODO Try to create list using \n? Maybe but think about benefits / downside on the collection recipe details page
        instructions = answer.split("**Instructions:**")[1].replace("\n\n", "")
        return instructions

    def generate_image_for_recipe(self, answer: str) -> str | None:
        project_id = os.getenv("PROJECT_ID")
        prompt = f"As a professional photographer specializing in 100mm Macro lens natural lightning food photography, please create a photorealistic, colorful, visually appealing image for use in a recipe collection webpage of a single serving for the following recipe: {answer}"
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")

        images = model.generate_images(
            prompt=prompt,
            # Optional parameters
            number_of_images=1,
            aspect_ratio="4:3",
            # TODO Implement if google adds support for parametrizing to JPEG directly
            # mime_type="image/jpeg",
        )

        local_file_path = "tmp/output.jpg"
        images[0].save(local_file_path, False)
        # TODO After upload should clear tmp
        return self.upload_image_to_gcs(project_id, local_file_path)

    def upload_image_to_gcs(self, project_id: str, local_file_path: str) -> str:
        """
            Uploads a file to Firebase Storage and returns its public URL.

            Args:
                project_id (str): Your GCP project ID.
                local_file (str): Path to the local file you want to upload.
                destination_blob_name (str): The destination path within the bucket (e.g., "recipes/output.jpg").

            Returns:
                str: The public URL of the uploaded file.
            """
        # Initialize a Cloud Storage client
        storage_client = storage.Client(project=project_id)

        # Set the bucket name.
        # Verify your bucket name in your Firebase Console.
        bucket_name = f"{project_id}.firebasestorage.app"
        bucket = storage_client.get_bucket(bucket_name)

        # Create a new blob and upload the file's content.
        blob = bucket.blob(f"recipes/{uuid.uuid4()}")
        blob.upload_from_filename(local_file_path)
        return blob.public_url

    def is_in_favourites(self, answer: str) -> bool:
        return answer in self.favourites

    async def load_recipe(self):
        """Load recipe details based on the 'id' query parameter."""
        recipe_id = self.router.page.full_raw_path.split("=")[1]
        if recipe_id:
            recipe_data = self.load_favourite_recipe(recipe_id)
            if recipe_data:
                self.selected_recipe = recipe_data
        else:
            self.selected_recipe = None

    @staticmethod
    def load_favourite_recipe(recipe_id: str) -> Recipe | None:
        ref = db.reference(FAVOURITES_KEY + "/" + recipe_id)
        recipe_data = ref.get()
        if recipe_data:
            return State.parse_recipe(recipe_data)
        return None

    @staticmethod
    def parse_recipe(recipe_data):
        recipe_json = json.loads(recipe_data)
        return Recipe(id=recipe_json["id"], title=recipe_json["title"], image_url=recipe_json["imageUrl"],
                      summary=recipe_json["summary"], ingredients=recipe_json["ingredients"],
                      instructions=recipe_json["instructions"])

    def toggle_view(self):
        """Toggle between showing ingredients and instructions."""
        self.show_ingredients = not self.show_ingredients

    async def load_recipes_list(self):
        self.favourites_recipes_list = self.load_favourite_recipes()

    @staticmethod
    def load_favourite_recipes() -> list[Recipe] | None:
        ref = db.reference(FAVOURITES_KEY)
        favourites = list(ref.get().items())
        if len(favourites) == 0:
            return None
        return [State.parse_recipe(recipe_entry[1]) for recipe_entry in favourites]

    async def redirect_to_recipe(self, id: str):
        return rx.redirect(f"/recipe?id={id}")
