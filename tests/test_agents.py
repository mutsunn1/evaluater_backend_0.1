"""Tests for agent factory functions — verify they return correctly structured oxygent entries."""

import pytest


class TestGeneratorAgentFactory:
    def test_returns_list(self):
        from agents.generator_agent import build_generator_agent
        result = build_generator_agent()
        assert isinstance(result, list)
        assert len(result) == 2  # time_tools + ReActAgent

    def test_contains_react_agent(self):
        from oxygent import oxy
        from agents.generator_agent import build_generator_agent
        result = build_generator_agent()
        agents = [x for x in result if isinstance(x, oxy.ReActAgent)]
        assert len(agents) == 1
        assert agents[0].name == "generator_agent"

    def test_has_tools(self):
        from agents.generator_agent import build_generator_agent
        result = build_generator_agent()
        agent = [x for x in result if hasattr(x, "name") and x.name == "generator_agent"][0]
        assert "time_tools" in agent.tools


class TestItemQAAgentFactory:
    def test_returns_list(self):
        from agents.item_qa_agent import build_item_qa_agent
        result = build_item_qa_agent()
        assert isinstance(result, list)

    def test_contains_chat_agent(self):
        from oxygent import oxy
        from agents.item_qa_agent import build_item_qa_agent
        result = build_item_qa_agent()
        agents = [x for x in result if isinstance(x, oxy.ChatAgent)]
        assert len(agents) == 1
        assert agents[0].name == "item_qa_agent"


class TestUserObserverAgentFactory:
    def test_returns_list(self):
        from agents.user_observer_agent import build_user_observer_agent
        result = build_user_observer_agent()
        assert isinstance(result, list)

    def test_contains_chat_agent(self):
        from oxygent import oxy
        from agents.user_observer_agent import build_user_observer_agent
        result = build_user_observer_agent()
        agents = [x for x in result if isinstance(x, oxy.ChatAgent)]
        assert len(agents) == 1
        assert agents[0].name == "user_observer_agent"


class TestGradingAgentFactory:
    def test_returns_list(self):
        from agents.grading_agent import build_grading_agent
        result = build_grading_agent()
        assert isinstance(result, list)

    def test_contains_react_agent(self):
        from oxygent import oxy
        from agents.grading_agent import build_grading_agent
        result = build_grading_agent()
        agents = [x for x in result if isinstance(x, oxy.ReActAgent)]
        assert len(agents) == 1
        assert agents[0].name == "grading_agent"


class TestMemoryMgmtAgentFactory:
    def test_returns_list(self):
        from agents.memory_mgmt_agent import build_memory_mgmt_agent
        result = build_memory_mgmt_agent()
        assert isinstance(result, list)

    def test_contains_react_agent(self):
        from oxygent import oxy
        from agents.memory_mgmt_agent import build_memory_mgmt_agent
        result = build_memory_mgmt_agent()
        agents = [x for x in result if isinstance(x, oxy.ReActAgent)]
        assert len(agents) == 1
        assert agents[0].name == "memory_mgmt_agent"


class TestMasterAgentFactory:
    def test_returns_list(self):
        from agents.master_agent import build_master_agent
        result = build_master_agent()
        assert isinstance(result, list)

    def test_is_master_true(self):
        from oxygent import oxy
        from agents.master_agent import build_master_agent
        result = build_master_agent()
        agents = [x for x in result if isinstance(x, oxy.ReActAgent)]
        assert len(agents) == 1
        assert agents[0].is_master is True
        assert agents[0].name == "master_agent"

    def test_has_all_sub_agents(self):
        from agents.master_agent import build_master_agent
        result = build_master_agent()
        agent = [x for x in result if hasattr(x, "is_master") and x.is_master][0]
        expected = {"generator_agent", "item_qa_agent", "user_observer_agent",
                    "grading_agent", "memory_mgmt_agent"}
        assert set(agent.sub_agents) == expected


class TestOxySpaceComposition:
    """Verify that all factories together produce a valid oxy_space."""

    def test_no_duplicate_names(self):
        from oxygent import oxy, preset_tools
        from agents.generator_agent import build_generator_agent
        from agents.item_qa_agent import build_item_qa_agent
        from agents.user_observer_agent import build_user_observer_agent
        from agents.grading_agent import build_grading_agent
        from agents.memory_mgmt_agent import build_memory_mgmt_agent
        from agents.master_agent import build_master_agent

        oxy_space = [
            oxy.HttpLLM(name="default_llm", api_key="test", base_url="http://test", model_name="test"),
            *build_generator_agent(),
            *build_item_qa_agent(),
            *build_user_observer_agent(),
            *build_grading_agent(),
            *build_memory_mgmt_agent(),
            *build_master_agent(),
        ]

        # Collect names of all agents
        names = [x.name for x in oxy_space if hasattr(x, "name")]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_all_agents_have_descriptions(self):
        from agents.generator_agent import build_generator_agent
        from agents.item_qa_agent import build_item_qa_agent
        from agents.user_observer_agent import build_user_observer_agent
        from agents.grading_agent import build_grading_agent
        from agents.memory_mgmt_agent import build_memory_mgmt_agent
        from agents.master_agent import build_master_agent

        all_factories = [
            build_generator_agent(),
            build_item_qa_agent(),
            build_user_observer_agent(),
            build_grading_agent(),
            build_memory_mgmt_agent(),
            build_master_agent(),
        ]

        for entries in all_factories:
            for entry in entries:
                # Only check agents, not tools (FunctionHub, etc.)
                if hasattr(entry, "name") and hasattr(entry, "is_master"):
                    assert entry.desc, f"Agent {entry.name} has no description"
