from services.ingestion.parsers.base import ChunkData


class ChunkService:
    CHUNK_SIZE = 3200
    CHUNK_OVERLAP = 400

    def split_pages(self, pages) -> list[ChunkData]:
        chunks = []
        chunk_index = 0

        for page in pages:
            page_text = page["text"]

            if not page_text.strip():
                continue

            start = 0
            while start < len(page_text):
                end = min(start + self.CHUNK_SIZE, len(page_text))
                text = page_text[start:end].strip()

                if text:
                    chunks.append(
                        ChunkData(
                            text=text,
                            chunk_index=chunk_index,
                            page_number=page["page_number"]
                        )
                    )
                    chunk_index += 1

                if end >= len(page_text):
                    break

                start = end - self.CHUNK_OVERLAP

        return chunks
