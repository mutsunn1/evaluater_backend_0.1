from oxygent import oxy


def build_generator_agent() -> list:
    return [
        oxy.ChatAgent(
            name="generator_agent",
            desc="A question generator that produces specific Chinese language "
                 "assessment items. Given instructions about scene, grammar_focus, "
                 "target_level, and question_type, generate a concrete question that "
                 "follows all constraints. Question types: multiple_choice, true_false, "
                 "fill_in_blank, reading_comprehension.",
            short_memory_size=0,  # skip ES history loading
        ),
    ]
