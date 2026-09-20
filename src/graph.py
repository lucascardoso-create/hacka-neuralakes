from .intake import intake_document
from .nodes import create_research_plan, finalize, normalize_demand, research
from .schemas import ResearchState

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:
    END = START = StateGraph = None  # type: ignore[misc,assignment]


class FallbackGraph:
    """Executor de contingência: preserva nós e estado enquanto LangGraph não instala."""

    def invoke(self, state: ResearchState) -> ResearchState:
        for node in (intake_document, normalize_demand, create_research_plan, research, finalize):
            state.update(node(state))
        return state


def build_graph():
    if StateGraph is None:
        return FallbackGraph()
    graph = StateGraph(ResearchState)
    graph.add_node("intake_document", intake_document)
    graph.add_node("normalize_demand", normalize_demand)
    graph.add_node("create_research_plan", create_research_plan)
    graph.add_node("research", research)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "intake_document")
    graph.add_edge("intake_document", "normalize_demand")
    graph.add_edge("normalize_demand", "create_research_plan")
    graph.add_edge("create_research_plan", "research")
    graph.add_edge("research", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()
