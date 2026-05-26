
def build_answer_evaluator_prompt(query, context, answer):

    return f"""
            Evaluate the answer using the provided context.

            Return JSON only:

            {{
                "grounded": true/false,
                "complete": true/false,
                "confidence": 0.0-1.0,
                "reason":"short explanation"
            }}

            Question:
            {query}

            Context:
            {context}

            Answer:
            {answer}
            """
