from dataclasses import dataclass

from firebase_admin.auth import UserRecord


@dataclass
class User:
    uid: str
    display_name: str
    email: str

    @classmethod
    def from_user_record(cls, user_record: UserRecord | None) -> "User":
        if user_record is None:
            return None
        return User(user_record.uid, user_record.email, user_record.email)
