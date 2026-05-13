"""
Checkpoint management for LangGraph state persistence.
"""

import json
import os
import time
from typing import Dict, Any, Optional
from datetime import datetime

from supply_chain_agent.config import settings
from supply_chain_agent.memory.vector_store import memory_manager


class CheckpointManager:
    """Manages checkpoints for LangGraph state."""

    def __init__(self, checkpoint_dir: str = "./data/checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        self._ensure_directory()

    def _ensure_directory(self):
        """Ensure checkpoint directory exists."""
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def save_checkpoint(self, state: Dict[str, Any], checkpoint_id: str,
                       metadata: Optional[Dict[str, Any]] = None):
        """
        Save a checkpoint.

        Args:
            state: State to save
            checkpoint_id: Unique checkpoint identifier
            metadata: Optional metadata
        """
        checkpoint_path = os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")

        checkpoint_data = {
            "state": state,
            "metadata": metadata or {},
            "timestamp": time.time(),
            "timestamp_iso": datetime.now().isoformat(),
            "checkpoint_id": checkpoint_id
        }

        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)

        # Also record in memory system
        memory_manager.record_agent_action(
            agent_name="checkpoint",
            action="save",
            details={
                "checkpoint_id": checkpoint_id,
                "state_keys": list(state.keys())
            },
            importance=0.6
        )

        print(f"✅ Checkpoint saved: {checkpoint_id}")

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a checkpoint.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint data or None if not found
        """
        checkpoint_path = os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")

        if not os.path.exists(checkpoint_path):
            return None

        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)

            # Record in memory system
            memory_manager.record_agent_action(
                agent_name="checkpoint",
                action="load",
                details={
                    "checkpoint_id": checkpoint_id,
                    "state_keys": list(checkpoint_data.get("state", {}).keys())
                },
                importance=0.5
            )

            print(f"✅ Checkpoint loaded: {checkpoint_id}")
            return checkpoint_data

        except Exception as e:
            print(f"❌ Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def list_checkpoints(self, limit: int = 10) -> list[Dict[str, Any]]:
        """
        List available checkpoints.

        Args:
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint summaries
        """
        if not os.path.exists(self.checkpoint_dir):
            return []

        checkpoints = []
        for filename in os.listdir(self.checkpoint_dir):
            if filename.endswith('.json'):
                checkpoint_path = os.path.join(self.checkpoint_dir, filename)
                try:
                    with open(checkpoint_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    checkpoints.append({
                        "id": data.get("checkpoint_id", filename[:-5]),
                        "timestamp": data.get("timestamp_iso", ""),
                        "state_keys": list(data.get("state", {}).keys()),
                        "metadata": data.get("metadata", {})
                    })
                except Exception:
                    # Skip corrupted checkpoints
                    continue

        # Sort by timestamp (newest first)
        checkpoints.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return checkpoints[:limit]

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            True if deleted, False otherwise
        """
        checkpoint_path = os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")

        if os.path.exists(checkpoint_path):
            try:
                os.remove(checkpoint_path)

                # Record in memory system
                memory_manager.record_agent_action(
                    agent_name="checkpoint",
                    action="delete",
                    details={"checkpoint_id": checkpoint_id},
                    importance=0.4
                )

                print(f"✅ Checkpoint deleted: {checkpoint_id}")
                return True
            except Exception as e:
                print(f"❌ Failed to delete checkpoint {checkpoint_id}: {e}")
                return False
        else:
            print(f"⚠️ Checkpoint not found: {checkpoint_id}")
            return False

    def cleanup_old_checkpoints(self, max_age_hours: int = 24):
        """
        Clean up old checkpoints.

        Args:
            max_age_hours: Maximum age in hours
        """
        if not os.path.exists(self.checkpoint_dir):
            return

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        deleted_count = 0
        for filename in os.listdir(self.checkpoint_dir):
            if filename.endswith('.json'):
                checkpoint_path = os.path.join(self.checkpoint_dir, filename)
                try:
                    file_mtime = os.path.getmtime(checkpoint_path)
                    if current_time - file_mtime > max_age_seconds:
                        os.remove(checkpoint_path)
                        deleted_count += 1
                except Exception:
                    continue

        if deleted_count > 0:
            print(f"🧹 Cleaned up {deleted_count} old checkpoints")

    def get_checkpoint_stats(self) -> Dict[str, Any]:
        """
        Get checkpoint statistics.

        Returns:
            Statistics about checkpoints
        """
        if not os.path.exists(self.checkpoint_dir):
            return {"total": 0, "directory": self.checkpoint_dir}

        checkpoints = self.list_checkpoints(limit=1000)  # Get all
        total = len(checkpoints)

        # Calculate total state size
        total_state_keys = 0
        for checkpoint in checkpoints:
            total_state_keys += len(checkpoint.get("state_keys", []))

        # Find oldest and newest
        timestamps = [cp.get("timestamp", "") for cp in checkpoints if cp.get("timestamp")]
        if timestamps:
            oldest = min(timestamps)
            newest = max(timestamps)
        else:
            oldest = newest = "N/A"

        return {
            "total": total,
            "total_state_keys": total_state_keys,
            "avg_state_keys": total_state_keys / total if total > 0 else 0,
            "oldest": oldest,
            "newest": newest,
            "directory": self.checkpoint_dir
        }


# Global checkpoint manager instance
checkpoint_manager = CheckpointManager()