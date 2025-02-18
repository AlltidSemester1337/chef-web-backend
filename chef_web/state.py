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

from chef_web.auth.auth_service import AuthService
from chef_web.model.recipe import Recipe
from chef_web.model.user import User

# TODO Move to auth or firebase later
ALLOWED_UIDS = ["fMo7MVYy3Sg7Q5VirSLQpX6H4OD2", "AuPP3gxW5fSjcxNB3NTQ9CVX9IJ2"]

CHAT_HISTORY_KEY = "chat_history"
USERS_KEY = "users"
RECIPES_KEY = "recipes"
PROJECT_ID = os.getenv("PROJECT_ID")

log = logging.getLogger(__name__)


class State(rx.State):
    # The current question being asked.
    question: str

    # Keep track of the chat history as a list of (question, answer) tuples.
    chat_history: list[tuple[str, str]]

    # state to track selected recipe on detail page
    selected_recipe: Recipe | None = None
    # Boolean to track which view to show on detail page.
    show_ingredients: bool = True

    # List of all favourite recipes
    favourites_recipes_list: list[Recipe]
    answers_in_favourites: dict[str, bool] = {}
    user_email: str | None = None
    user: User | None = None
    redirect_to: str | None = None

    # Function to fetch chat history from Firebase
    def load_history(self) -> list[tuple[str, str]]:
        ref = db.reference(USERS_KEY + "/" + self.user.uid + "/" + CHAT_HISTORY_KEY)
        chat_data = ref.get()
        if chat_data:
            chat_history = list(chat_data.items())
            res = []
            # Format timestamps for display
            for i in range(0, len(chat_history), 2):
                question_entry = chat_history[i][1]
                answer_entry = chat_history[i + 1][1]
                if question_entry and answer_entry:
                    question = question_entry.get("parts", [{}])[0].get("text", "")
                    answer = answer_entry.get("parts", [{}])[0].get("text", "")
                    if self.answer_is_in_favourites(answer):
                        self.answers_in_favourites[answer] = True
                    res += (question, answer),
            return res
        return []

    async def check_user_permissions(self):
        if self.user is None or self.user.uid not in ALLOWED_UIDS:
            return rx.redirect("/login")
        await self.load_recipes_list()
        self.chat_history = self.load_history()

    @rx.event
    async def answer(self):
        location = "europe-north1"

        vertexai.init(
            project=PROJECT_ID,
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

        model = GenerativeModel("gemini-2.0-flash-001", generation_config=parameters,
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
            ref = db.reference(USERS_KEY + "/" + self.user.uid + "/" + CHAT_HISTORY_KEY)

            try:
                # TODO look further into tx issues, or how to deal with potential corruption?
                ref.push().set({
                    "parts": [
                        {"text": original_question},
                    ],
                    "role": "user",
                })
                ref.push().set({
                    "parts": [
                        {"text": answer},
                    ],
                    "role": "model",
                })
            except Exception as e:
                logging.error(f"Error saving chatHistory: {e}", exc_info=True)

    async def stream_response(self, chat: ChatSession, question: str) -> AsyncIterable[GenerationResponse]:
        for chunk in chat.send_message(question, stream=True):
            yield chunk

    @rx.event
    async def add_to_favourites(self, answer: str):
        """Add the selected recipe to the Firebase 'favourites' table."""
        try:
            title = self.derive_recipe_title(answer)
            summary = self.derive_recipe_summary(answer, title=title)
            ingredients = self.derive_recipe_ingredients(answer, title=title, summary=summary)
            instructions = self.derive_recipe_instructions(answer)
        except Exception as e:
            log.warning(f"Error derive details from recipe: {e}", exc_info=True)
            return

        if await self.title_is_in_favourites(title):
            log.debug(f"Recipe already in favourites: {title}")
            return

        try:
            image_url = self.generate_image_for_recipe(answer)
        except Exception as e:
            log.warning(f"Error generating image for recipe: {e}", exc_info=True)
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
            "uid": self.user.uid,
        }
        ref = db.reference(RECIPES_KEY)

        try:
            # Push recipe entry to Firebase
            new_ref = ref.push()
            recipe_entry["id"] = new_ref.key
            new_ref.set(recipe_entry)
            log.info("Recipe saved successfully!")  # Debugging
        except Exception as e:
            log.error(f"Error saving recipe: {e}", exc_info=True)
        self.answers_in_favourites[answer] = True

    def answer_is_in_favourites(self, answer: str) -> bool:
        try:
            title = self.derive_recipe_title(answer)
        except Exception as _:
            return False
        return title in [recipe.title for recipe in self.favourites_recipes_list]

    async def title_is_in_favourites(self, title: str) -> bool:
        return title in [recipe.title for recipe in self.favourites_recipes_list]

    def derive_recipe_title(self, answer: str) -> str | None:
        """Derive the recipe title from the chatbot response."""
        title = answer.split("\n\n")[0].replace("##", "").lstrip()
        return title

    def derive_recipe_summary(self, answer: str, title: str) -> str | None:
        """Derive the recipe title from the chatbot response."""
        summary = answer.split("**Ingredients:**")[0].replace(title, "").replace("##  \n\n", "")
        return summary

    def derive_recipe_ingredients(self, answer: str, title: str, summary: str) -> str | None:
        """Derive the ingredients from the chatbot response."""
        ingredients = answer.split("**Instructions:**")[0].replace(title, "").replace(summary, "").replace("##  \n\n",
                                                                                                           "").replace(
            "**Ingredients:**\n\n", "")
        return ingredients

    def derive_recipe_instructions(self, answer: str) -> str | None:
        """Derive the instructions from the chatbot response."""
        instructions = answer.split("**Instructions:**")[1].replace("\n\n", "")
        return instructions

    def generate_image_for_recipe(self, answer: str) -> str | None:
        prompt = f"As a professional photographer specializing in 100mm Macro lens natural lightning food photography, please create a photorealistic, colorful, visually appealing image for use in a recipe collection webpage of a single serving for the following recipe: {answer}"
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")

        images = model.generate_images(
            prompt=prompt,
            # Optional parameters
            number_of_images=1,
            aspect_ratio="4:3",
        )

        local_file_path = os.getcwd() + "/tmp/output.jpg"
        images[0].save(local_file_path, False)

        public_url = self.upload_image_to_gcs(local_file_path)
        try:
            os.remove(local_file_path)
        except Exception as e:
            log.warning(f"Failed to remove tmp file: {e}", exc_info=True)
        return public_url

    def upload_image_to_gcs(self, local_file_path: str) -> str:
        """
            Uploads a file to Firebase Storage and returns its public URL.

            Args:
                local_file (str): Path to the local file you want to upload.
                destination_blob_name (str): The destination path within the bucket (e.g., "recipes/output.jpg").

            Returns:
                str: The public URL of the uploaded file.
            """
        # Initialize a Cloud Storage client
        storage_client = storage.Client(project=PROJECT_ID)

        # Set the bucket name.
        # Verify your bucket name in your Firebase Console.
        bucket_name = f"{PROJECT_ID}.firebasestorage.app"
        bucket = storage_client.get_bucket(bucket_name)

        # Create a new blob and upload the file's content.
        blob = bucket.blob(f"recipes/{uuid.uuid4()}")
        blob.upload_from_filename(local_file_path)
        blob.make_public()
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
        ref = db.reference(f"{RECIPES_KEY}/{recipe_id}")
        recipe_data = ref.get()
        return State.parse_recipe(recipe_data) if recipe_data else None

    @staticmethod
    def parse_recipe(recipe_data) -> Recipe:
        return Recipe(id=recipe_data.get("id"), title=recipe_data.get("title"), image_url=recipe_data.get("imageUrl"),
                      summary=recipe_data.get("summary"), ingredients=recipe_data.get("ingredients"),
                      instructions=recipe_data.get("instructions"))

    def toggle_view(self):
        """Toggle between showing ingredients and instructions."""
        self.show_ingredients = not self.show_ingredients

    async def load_recipes_list(self):
        self.favourites_recipes_list = self.load_favourite_recipes()

    def load_favourite_recipes(self) -> list[Recipe] | None:
        ref = db.reference(RECIPES_KEY)
        if self.user is None:
            favourites = ref.get()
        else:
            favourites = ref.order_by_child("uid").equal_to(self.user.uid).get()
        if not favourites:
            return None
        return [State.parse_recipe(recipe_entry) for recipe_entry in favourites.values()]

    async def redirect_to_recipe(self, id: str):
        return rx.redirect(f"/recipe?id={id}")

    @rx.event
    async def login_sign_up(self) -> None:
        if self.user_email is None:
            raise Exception("User is not set")
        auth_service = AuthService()
        fixed_password = "-------"
        self.user = User.from_user_record(auth_service.sign_in_email_password(self.user_email, fixed_password))
        # Sign up
        if not self.user:
            self.user = User.from_user_record(auth_service.create_user(self.user_email, fixed_password))
        self.redirect_to = "/recipes"

    @rx.event
    async def logout(self):
        self.user = None
        self.user_email = None
        self.redirect_to = None
        return rx.redirect("/login")
