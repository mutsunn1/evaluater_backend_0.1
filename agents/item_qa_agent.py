from oxygent import oxy


def build_item_qa_agent() -> list:
    return [
        oxy.ChatAgent(
            name="item_qa_agent",
            desc="A quality inspector for generated Chinese assessment items. Given a question "
                 "produced by generator_agent and the original instruction package from Master "
                 "Agent (including forbidden_list, target_level, grammar_focus, question_type), "
                 "check: 1) Does the question use forbidden words? 2) Does it match the target "
                 "HSK level? 3) Does it test the specified grammar focus? 4) Is the question "
                 "type format correct (options for MC, blanks for FIB, etc.)? 5) Is the scene "
                 "logically continuous with previous items? Return PASS or FAIL with specific "
                 "reasons for each check.",
            short_memory_size=0,
        ),
    ]
