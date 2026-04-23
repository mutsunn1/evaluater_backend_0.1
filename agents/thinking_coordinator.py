"""Thinking coordinator: uses oxygent's native ParallelAgent to collect per-agent thinking outputs."""

from oxygent import oxy


def build_thinking_coordinator() -> list:
    """Register a ParallelAgent that fans out to all sub-agents and summarizes their thinking."""
    return [
        oxy.ParallelAgent(
            name="thinking_coordinator",
            desc="A thinking coordinator that runs generator_agent, item_qa_agent, "
                 "user_observer_agent, grading_agent, and memory_mgmt_agent in parallel, "
                 "then summarizes their outputs into a concise thinking report.",
            permitted_tool_name_list=[
                "generator_agent",
                "item_qa_agent",
                "user_observer_agent",
                "grading_agent",
                "memory_mgmt_agent",
            ],
            llm_model="default_llm",
            short_memory_size=0,
        ),
    ]
