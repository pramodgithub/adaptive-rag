
def build_query_rewriter_prompt(query, context):

    return f"""
Rewrite the query only to improve retrieval quality.

Rules:
- Preserve original meaning exactly
- Do not introduce new domains
- Do not invent assumptions
- Keep important keywords
- Expand abbreviations if needed
- Return only rewritten query

Original query:

{query}

Current context:

{context}
"""
