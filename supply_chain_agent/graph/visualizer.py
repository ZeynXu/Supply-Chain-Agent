"""
Visualization module for Supply Chain Agent workflow.

Provides real-time visualization of LangGraph state transitions and agent activities.
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import io
import base64

from supply_chain_agent.graph.workflow import workflow
from supply_chain_agent.memory.vector_store import memory_manager


class WorkflowVisualizer:
    """Visualizes the LangGraph workflow state."""

    def __init__(self):
        self.graph_history: List[Dict[str, Any]] = []
        self.max_history = 100

    def record_state_transition(self, from_node: str, to_node: str,
                               state: Dict[str, Any], condition: str = ""):
        """Record a state transition."""
        transition = {
            "timestamp": time.time(),
            "timestamp_iso": datetime.now().isoformat(),
            "from_node": from_node,
            "to_node": to_node,
            "state_keys": list(state.keys()),
            "condition": condition,
            "state_summary": self._get_state_summary(state)
        }

        self.graph_history.append(transition)

        # Keep history size limited
        if len(self.graph_history) > self.max_history:
            self.graph_history = self.graph_history[-self.max_history:]

        # Also record in memory system
        memory_manager.record_agent_action(
            agent_name="visualizer",
            action="state_transition",
            details={
                "from": from_node,
                "to": to_node,
                "condition": condition
            },
            importance=0.5
        )

    def _get_state_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of the state."""
        return {
            "has_intent": bool(state.get("user_intent")),
            "intent_type": state.get("user_intent", {}).get("intent_level_1", "unknown"),
            "missing_slots": len(state.get("missing_slots", [])),
            "task_queue_length": len(state.get("task_queue", [])),
            "tool_results_count": len(state.get("tool_results", {})),
            "audit_passed": state.get("audit_results", {}).get("passed", False),
            "error_count": state.get("error_count", 0)
        }

    def get_workflow_graph(self) -> nx.DiGraph:
        """Create a NetworkX graph representation of the workflow."""
        G = nx.DiGraph()

        # Get workflow info
        workflow_info = workflow.get_graph_info()

        # Add nodes
        for node in workflow_info["nodes"]:
            G.add_node(node, type="node")

        # Add edges (simplified representation)
        edges = [
            ("parse_input", "clarify"),
            ("parse_input", "plan_task"),
            ("clarify", "plan_task"),
            ("plan_task", "execute_task"),
            ("plan_task", "handle_error"),
            ("execute_task", "audit"),
            ("execute_task", "retry"),
            ("retry", "execute_task"),
            ("retry", "handle_error"),
            ("audit", "generate_report"),
            ("audit", "handle_error"),
            ("generate_report", "END"),
            ("handle_error", "END")
        ]

        for from_node, to_node in edges:
            if from_node in G and to_node in G:
                G.add_edge(from_node, to_node)

        return G

    def create_graph_image(self) -> str:
        """
        Create a base64 encoded image of the workflow graph.

        Returns:
            Base64 encoded PNG image
        """
        try:
            G = self.get_workflow_graph()

            # Create figure
            plt.figure(figsize=(12, 8))

            # Use spring layout
            pos = nx.spring_layout(G, seed=42)

            # Define node colors by type
            node_colors = []
            for node in G.nodes():
                if node == "parse_input":
                    node_colors.append("#4CAF50")  # Green
                elif node == "execute_task":
                    node_colors.append("#2196F3")  # Blue
                elif node == "audit":
                    node_colors.append("#FF9800")  # Orange
                elif node == "handle_error" or node == "retry":
                    node_colors.append("#F44336")  # Red
                elif node == "generate_report":
                    node_colors.append("#9C27B0")  # Purple
                else:
                    node_colors.append("#9E9E9E")  # Grey

            # Draw the graph
            nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                                  node_size=2000, alpha=0.8)
            nx.draw_networkx_edges(G, pos, arrowstyle='->', arrowsize=20,
                                  edge_color='#555555', width=2, alpha=0.7)
            nx.draw_networkx_labels(G, pos, font_size=12, font_weight='bold')

            # Add title
            plt.title("Supply Chain Agent Workflow Graph", fontsize=16, fontweight='bold')
            plt.axis('off')

            # Convert to base64
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            plt.close()

            buf.seek(0)
            image_base64 = base64.b64encode(buf.read()).decode('utf-8')

            return image_base64

        except Exception as e:
            print(f"Error creating graph image: {e}")
            return ""

    def get_recent_transitions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent state transitions."""
        recent = self.graph_history[-limit:] if self.graph_history else []
        return recent

    def get_transition_stats(self) -> Dict[str, Any]:
        """Get statistics about state transitions."""
        if not self.graph_history:
            return {"total_transitions": 0}

        transitions = self.graph_history

        # Count transitions by node
        node_counts = {}
        for transition in transitions:
            from_node = transition["from_node"]
            to_node = transition["to_node"]

            node_counts[from_node] = node_counts.get(from_node, 0) + 1
            node_counts[to_node] = node_counts.get(to_node, 0) + 1

        # Calculate success/failure rates (simplified)
        success_count = sum(1 for t in transitions if t["to_node"] not in ["handle_error", "retry"])
        total_count = len(transitions)
        success_rate = success_count / total_count if total_count > 0 else 0

        # Find most common paths
        path_counts = {}
        for transition in transitions:
            path = f"{transition['from_node']}→{transition['to_node']}"
            path_counts[path] = path_counts.get(path, 0) + 1

        most_common_paths = sorted(path_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_transitions": total_count,
            "success_rate": success_rate,
            "most_active_nodes": sorted(node_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            "most_common_paths": most_common_paths,
            "time_range": {
                "first": transitions[0]["timestamp_iso"] if transitions else None,
                "last": transitions[-1]["timestamp_iso"] if transitions else None
            }
        }

    def create_state_timeline(self) -> List[Dict[str, Any]]:
        """Create a timeline of state transitions."""
        if not self.graph_history:
            return []

        timeline = []
        for i, transition in enumerate(self.graph_history):
            timeline.append({
                "id": i + 1,
                "time": transition["timestamp_iso"],
                "from": transition["from_node"],
                "to": transition["to_node"],
                "condition": transition["condition"],
                "state_summary": transition["state_summary"]
            })

        return timeline

    def generate_workflow_report(self) -> Dict[str, Any]:
        """Generate a comprehensive workflow report."""
        graph_image = self.create_graph_image()
        recent_transitions = self.get_recent_transitions(5)
        transition_stats = self.get_transition_stats()
        timeline = self.create_state_timeline()[:20]  # Last 20 transitions

        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_transitions": len(self.graph_history),
                "graph_nodes": list(self.get_workflow_graph().nodes())
            },
            "visualization": {
                "graph_image_available": bool(graph_image),
                "graph_image": graph_image[:100] + "..." if graph_image else ""
            },
            "statistics": transition_stats,
            "recent_activity": {
                "transitions": recent_transitions,
                "timeline": timeline
            },
            "analysis": {
                "bottlenecks": self._identify_bottlenecks(),
                "recommendations": self._generate_recommendations()
            }
        }

        return report

    def _identify_bottlenecks(self) -> List[str]:
        """Identify potential bottlenecks in the workflow."""
        bottlenecks = []

        if not self.graph_history:
            return bottlenecks

        # Count error handler usage
        error_transitions = sum(1 for t in self.graph_history
                              if t["to_node"] == "handle_error")
        total_transitions = len(self.graph_history)

        if total_transitions > 0 and error_transitions / total_transitions > 0.2:
            bottlenecks.append("高错误率：超过20%的流转进入错误处理")

        # Check for frequent retries
        retry_transitions = sum(1 for t in self.graph_history
                              if t["to_node"] == "retry")
        if retry_transitions > 5:
            bottlenecks.append("频繁重试：工具调用可能需要优化")

        # Check clarification frequency
        clarification_transitions = sum(1 for t in self.graph_history
                                      if t["from_node"] == "clarify")
        if clarification_transitions > 10:
            bottlenecks.append("频繁澄清：意图识别可能需要改进")

        return bottlenecks

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on workflow analysis."""
        recommendations = []

        if not self.graph_history:
            return ["尚无足够数据进行分析"]

        stats = self.get_transition_stats()

        if stats["success_rate"] < 0.7:
            recommendations.append("优化工作流成功率：检查错误处理和重试逻辑")

        # Check if any node is too active (potential bottleneck)
        for node, count in stats.get("most_active_nodes", []):
            if count > 20:  # Arbitrary threshold
                recommendations.append(f"节点 {node} 活动频繁，考虑优化")

        # Check for long processing times (simplified)
        if len(self.graph_history) > 10:
            recommendations.append("考虑增加并发处理能力")

        if not recommendations:
            recommendations.append("工作流表现良好，继续保持监控")

        return recommendations


# Global visualizer instance
workflow_visualizer = WorkflowVisualizer()