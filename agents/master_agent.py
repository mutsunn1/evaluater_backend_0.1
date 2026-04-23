from oxygent import oxy


def build_master_agent() -> list:
    return [
        oxy.ReActAgent(
            is_master=True,
            name="master_agent",
            desc="The moderator and state machine manager of the Chinese proficiency assessment "
                 "system. Coordinates generator_agent, item_qa_agent, user_observer_agent, "
                 "grading_agent, and memory_mgmt_agent. Responsibilities: 1) Context aggregation: "
                 "read session_events history before each round. 2) Path planning: decide tactical "
                 "goals based on language function sequence. 3) Parametric instructions: generate "
                 "high-concentration JSON packages (must_include, forbidden_list, target_level, "
                 "scene, question_type, grammar_focus) for generator_agent. 4) Evaluation "
                 "adjudication: at session end, determine level promotion/demotion. Task pointers: "
                 "planning, generating, quality_checking, waiting_answer, analyzing, persisting, "
                 "session_ending, retrying.",
            sub_agents=[
                "generator_agent",
                "item_qa_agent",
                "user_observer_agent",
                "grading_agent",
                "memory_mgmt_agent",
            ],
        ),
    ]
