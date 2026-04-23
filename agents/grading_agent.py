from oxygent import oxy


def build_grading_agent() -> list:
    return [
        oxy.ReActAgent(
            name="grading_agent",
            desc="A language proficiency grading expert that evaluates Chinese language "
                 "assessment responses across four dimensions: character (汉字), vocabulary "
                 "(词汇), sentence (句子), and pragmatics (语用). For each dimension, provide: "
                 "score (out of 10), specific evidence for deductions with grammatical reasoning "
                 "(Chain of Thought required), and highlight persistent errors or excellent "
                 "expressions. Also incorporate TTR (Type-Token Ratio) data if available from "
                 "the math engine. Return a structured JSON with all four dimension scores, "
                 "total score, and tagged highlights/errors for memory management.",
            short_memory_size=0,
        ),
    ]
