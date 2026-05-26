from pydantic import BaseModel

from core.llm.prompts.query_rewriter_prompt import build_query_rewriter_prompt
from core.llm.router import ModelRouter


class QueryRewriteResponse(BaseModel):
    query: str


class QueryRewriter:

    def __init__(self):
        self.llm = ModelRouter()

    def rewrite(self, query: str, context: str) -> str:

        prompt = build_query_rewriter_prompt(query, context)

        response = self.llm.generate(prompt)

        rewritten_query = response["text"].strip()

        return rewritten_query
