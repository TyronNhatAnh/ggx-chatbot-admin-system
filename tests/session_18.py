"""Session 18 — Graph Traversal & Flow Tracing (find_api_consumers, traverse_graph, get_knowledge_stats)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'Which services does the GetOrderDetail handler call? Traverse the graph to find out',
    'Which frontend pages call the API /orders/:orderId?',
    'Find all API consumers of the /admin/orders creation endpoint',
    'How many enums and structs have been indexed? (get_knowledge_stats)',
    'Traverse the graph from OrderAPIs.getOrder in the outgoing direction',
]

if __name__ == "__main__":
    run_session(18, "Graph Traversal & Flow Tracing (find_api_consumers, traverse_graph, get_knowledge_stats)", QUESTIONS)
