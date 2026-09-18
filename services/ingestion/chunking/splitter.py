import re

from .models import DocumentChunk


class ChunkSizeSplitter:
    MAX_CHARS = 3200
    OVERLAP_CHARS = 400

    def split(
        self,
        chunk: DocumentChunk,
    ) -> list[DocumentChunk]:
        if len(chunk.text) <= self.MAX_CHARS:
            return [chunk]

        segments = self._split_into_segments(chunk.text)

        parts: list[str] = []
        current: list[str] = []
        current_length = 0

        for segment in segments:
            segment_length = len(segment)

            if (
                current
                and current_length + segment_length + 2
                > self.MAX_CHARS
            ):
                parts.append("\n\n".join(current))
                current = []
                current_length = 0

            if segment_length > self.MAX_CHARS:
                if current:
                    parts.append("\n\n".join(current))
                    current = []
                    current_length = 0

                parts.extend(
                    self._hard_split(segment)
                )
                continue

            current.append(segment)
            current_length += (
                segment_length + 2
                if current_length
                else segment_length
            )

        if current:
            parts.append("\n\n".join(current))

        return [
            self._create_part(
                chunk=chunk,
                text=text,
                part_index=index,
            )
            for index, text in enumerate(parts)
            if text.strip()
        ]

    @staticmethod
    def _split_into_segments(text: str) -> list[str]:
        paragraphs = re.split(r"\n\s*\n", text)

        segments: list[str] = []

        for paragraph in paragraphs:
            paragraph = paragraph.strip()

            if not paragraph:
                continue

            if len(paragraph) <= ChunkSizeSplitter.MAX_CHARS:
                segments.append(paragraph)
                continue

            sentences = re.split(
                r"(?<=[.!?])\s+",
                paragraph,
            )

            segments.extend(
                sentence.strip()
                for sentence in sentences
                if sentence.strip()
            )

        return segments

    @classmethod
    def _hard_split(cls, text: str) -> list[str]:
        parts: list[str] = []

        start = 0

        while start < len(text):
            end = min(
                start + cls.MAX_CHARS,
                len(text),
            )

            part = text[start:end].strip()

            if part:
                parts.append(part)

            if end >= len(text):
                break

            start = max(
                0,
                end - cls.OVERLAP_CHARS,
            )

        return parts

    @staticmethod
    def _create_part(
        chunk: DocumentChunk,
        text: str,
        part_index: int,
    ) -> DocumentChunk:
        return DocumentChunk(
            chunk_index=chunk.chunk_index,
            text=text,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_path=list(chunk.section_path),
            structure_type=chunk.structure_type,
            identifier=chunk.identifier,
            parent_identifier=chunk.parent_identifier,
            element_indexes=list(chunk.element_indexes),
            metadata={
                **chunk.metadata,
                "split": True,
                "split_index": part_index,
            },
        )
