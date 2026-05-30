
def build_answer_evaluator_prompt(query, context, answer):

    return f"""
            You are a strict evaluator. Your job is to check if the answer 
            is supported by the context. Be conservative — when in doubt, mark false.

            Rules:
            - grounded: true ONLY if every claim in the answer has 
            direct evidence in the context. If even one claim is unsupported → false.
            - complete: true ONLY if the answer addresses ALL parts of the question.
            - confidence: your certainty in this evaluation (not the answer quality).
            - reason: cite the specific part of context that supports or contradicts.

            Return ONLY valid JSON. No explanation outside JSON.

            Question: {query}
            Context:  {context}
            Answer:   {answer}

            {{
                "grounded": true/false,
                "complete": true/false,
                "confidence": 0.0-1.0,
                "reason": "quote the context line that proves/disproves grounding"
            }}
            """
