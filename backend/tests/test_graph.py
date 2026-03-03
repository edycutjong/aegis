"""Tests for app.agent.graph — validate graph structure without running it."""


from app.agent.graph import build_agent_graph, agent_graph


class TestGraphStructure:
    """Verify the compiled graph has the correct nodes and edges."""

    def test_graph_has_all_expected_nodes(self):
        graph = build_agent_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "classify_intent",
            "validate_customer",
            "write_sql",
            "execute_sql",
            "search_docs",
            "propose_action",
            "await_approval",
            "execute_action",
            "generate_response",
            "__start__",
        }
        assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"

    def test_graph_has_name(self):
        graph = build_agent_graph()
        assert graph.name == "aegis-support-workflow"

    def test_graph_has_checkpointer(self):
        graph = build_agent_graph()
        assert graph.checkpointer is not None

    def test_module_level_graph_is_compiled(self):
        """The module-level `agent_graph` should be ready to use."""
        assert agent_graph is not None
        assert agent_graph.name == "aegis-support-workflow"

    def test_node_count(self):
        graph = build_agent_graph()
        # 9 user nodes (excluding __start__)
        user_nodes = {k for k in graph.nodes if not k.startswith("__")}
        assert len(user_nodes) == 9
