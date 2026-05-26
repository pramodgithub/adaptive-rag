
def build_retrieval_prompt(query, context):

    return f"""

                You are a RAG assistant.

                Answer only using the provided context.

                If context is insufficient say:

                "I couldn't find enough information."

                Context:

                {context}

                Question:

                {query}

                Answer:
            """
