from dataclasses import dataclass

@dataclass
class Recipe:
    id: str | None = None
    title: str = ""
    image_url: str | None = None
    summary: str = ""
    ingredients: str = ""
    instructions: str = ""
