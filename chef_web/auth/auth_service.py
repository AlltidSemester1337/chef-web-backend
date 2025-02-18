import os
import requests
from firebase_admin import auth

from firebase_admin.auth import UserRecord

WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")


class AuthService:
    currentUser: UserRecord | None = None

    def get_current_user(self) -> UserRecord | None:
        return self.currentUser

    def sign_in_email_password(self, email: str, password: str) -> UserRecord | None:
        auth_response = requests.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={WEB_API_KEY}",
            json={"email": f"{email}",
                  "password": f"{password}",
                  "returnSecureToken": True}).json()

        id_token = auth_response.get("idToken")
        if id_token:
            # TODO UID can be written to LS and read from there before prompting log in, used with sign_in_uid
            return auth.get_user_by_email(email)
        return None

    def sign_in_uid(self, uid: str) -> UserRecord:
        return auth.get_user(uid)

    def create_user(self, email: str, password: str) -> UserRecord:
        self.currentUser = auth.create_user(email=email, password=password)
        return self.currentUser

    def sign_out(self):
        # TODO LS delete UID if present
        self.currentUser = None

    def delete_user(self, uid: str) -> bool:
        # TODO Should clear up Firestore entries for user, possibly see extensions
        auth.delete_user(uid)
        return True
