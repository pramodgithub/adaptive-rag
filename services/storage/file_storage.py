import os
import uuid
import json


class FileStorage:

    BASE_PATH = "/documents"

    PROCESSED_PATH = "/processed"

    def save(self, content: bytes, filename: str) -> str:

        os.makedirs(self.BASE_PATH, exist_ok=True)

        file_id = uuid.uuid4()

        path = os.path.join(
            self.BASE_PATH,
            f"{file_id}_{filename}"
        )

        with open(path, "wb") as file:
            file.write(content)

        return path

    def save_text(self, text: str, filename: str) -> str:

        os.makedirs(self.PROCESSED_PATH, exist_ok=True)

        file_id = uuid.uuid4()

        path = os.path.join(
            self.PROCESSED_PATH,
            f"{file_id}_{filename}.txt"
        )

        with open(path, "w", encoding="utf-8") as file:
            file.write(text)

        return path

    def save_json(self, data: dict, filename: str) -> str:
        os.makedirs(self.PROCESSED_PATH, exist_ok=True)

        file_id = uuid.uuid4()
        path = os.path.join(self.PROCESSED_PATH, f"{file_id}_{filename}.json")

        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)

        return path
