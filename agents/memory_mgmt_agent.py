from oxygent import oxy


def build_memory_mgmt_agent() -> list:
    return [
        oxy.ReActAgent(
            name="memory_mgmt_agent",
            desc="A memory management agent responsible for CRUD operations on mid-term "
                 "(Elasticsearch vector) and long-term (PostgreSQL profile) memory. Supports "
                 "extraction protocols: Probe Mode (find unused vocabulary), Review Mode "
                 "(summarize top 3 failed grammar points), Sync Mode (identify discrepancies "
                 "between recent performance and long-term profile). Also handles persisting "
                 "highlight sentences, persistent errors, and interest topics flagged by "
                 "Master Agent. Question types: multiple_choice, fill_in_blank, true_false, "
                 "reading_comprehension.",
            short_memory_size=0,
        ),
    ]
