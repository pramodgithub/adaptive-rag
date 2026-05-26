from langchain_text_splitters import RecursiveCharacterTextSplitter


class ChunkService:

    def __init__(self):

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )

    def split(self, text: str):

        return self.splitter.split_text(
            text
        )
