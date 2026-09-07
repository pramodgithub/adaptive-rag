def build_retrieval_judge_prompt(query: str, context: str) -> str:
    return f"""
        You are a retrieval quality judge for a compliance-focused RAG system.

        Your task is to determine whether the retrieved evidence is sufficient
        to answer the user's question accurately.

        Evaluate ONLY the retrieved context provided below.

        Question:
        {query}

        Retrieved Context:
        {context}

        Evaluate the following:

        1. relevant
          - true if the retrieved evidence is substantively related to the question.
          - false if the evidence is mostly irrelevant.

        2. coverage
          - 0.0 means the question is essentially unanswered.
          - 1.0 means the retrieved evidence fully addresses the question.

        3. confidence
          - Your confidence that the retrieved evidence is sufficient to answer
            the question accurately.

        4. missing_evidence
          - Identify important information required to answer the question
            that is absent from the retrieved context.
          - Return an empty array if nothing important is missing.

        5. contradictions
          - Identify conflicting claims within the retrieved evidence.
          - Return an empty array if there are no contradictions.

        6. sufficient
          - true only when the retrieved evidence provides enough information
            to answer the question accurately without inventing information.

        7. reason
          - Briefly explain the judgment.

        Return ONLY valid JSON matching this structure:

        {{
            "relevant": true,
            "coverage": 0.0,
            "confidence": 0.0,
            "missing_evidence": [],
            "contradictions": [],
            "sufficient": true,
            "reason": ""
        }}
        """
