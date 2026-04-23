from oxygent import oxy


def build_user_observer_agent() -> list:
    return [
        oxy.ChatAgent(
            name="user_observer_agent",
            desc="A behavioral monitoring agent that analyzes user interaction patterns during "
                 "Chinese language assessment. Given the user's answer text, total time spent "
                 "on the item, number of clarification turns, and the item's expected duration "
                 "and difficulty, analyze: 1) Is the time spent normal or abnormal? 2) Is the "
                 "delay caused by Chinese language limitations or industry knowledge gaps? "
                 "3) Extract psychological labels (e.g., 'hesitant', 'confident', 'confused'). "
                 "Return a structured analysis with cause attribution percentages.",
            short_memory_size=0,
        ),
    ]
