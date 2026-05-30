
def build_retrieval_judge_prompt(query, context):

    return f"""
Question:
{query}

Retrieved Context:
{context}

Does the retrieved context contain
enough information to answer the question?

Return:

{{
  "relevant": true,
  "coverage": 0.0-1.0,
  "confidence": 0.0-1.0,
  "reason": ""
}}
"""
