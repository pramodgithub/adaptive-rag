def build_eval_retry_prompt(prompt):

    return f"""
            Answer strictly from provided context.

            Do not assume facts.

            {prompt}
            """
