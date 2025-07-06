import time
import asyncio
import logging
from typing import Dict, Any
from agent_base import AgentBase

logger = logging.getLogger(__name__)


class ExecutorAgent(AgentBase):
    """Agent that executes accepted tasks"""

    def __init__(self, agent_id: str):
        super().__init__(agent_id)
        self.execution_queue: Dict[str, Dict] = {}
        self.completed_tasks: Dict[str, Dict] = {}

    async def _subscribe_to_topics(self):
        """Subscribe to task responses to find accepted tasks"""
        topics = ["task-responses"]
        self.consumer.subscribe(topics)
        logger.info(f"ExecutorAgent {self.agent_id} subscribed to {topics}")

    async def _process_message(self, msg):
        """Process incoming messages"""
        topic = msg.topic

        try:
            if topic == "task-responses":
                await self._handle_task_response(msg)
        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")

    async def _handle_task_response(self, msg):
        """Handle task response messages to find accepted tasks"""
        try:
            response = self.deserialize_message("task_response", msg.value)

            # If a task is accepted, add it to execution queue
            if response["status"] == "ACCEPTED":
                task_id = response["task_id"]

                if (
                    task_id not in self.execution_queue
                    and task_id not in self.completed_tasks
                ):
                    self.execution_queue[task_id] = {
                        "response": response,
                        "status": "QUEUED",
                        "queued_at": time.time(),
                    }

                    logger.info(f"Added task {task_id} to execution queue")

                    # Start executing the task
                    asyncio.create_task(self._execute_task(task_id))

        except Exception as e:
            logger.error(f"Error handling task response: {e}")

    async def _execute_task(self, task_id: str):
        """Execute a task"""
        try:
            if task_id not in self.execution_queue:
                return

            task_info = self.execution_queue[task_id]
            task_info["status"] = "RUNNING"
            task_info["started_at"] = time.time()

            logger.info(f"Starting execution of task {task_id}")

            # Send running status
            await self._send_execution_status(task_id, "RUNNING")

            # Simulate task execution (replace with actual work)
            execution_time = 5  # 5 seconds
            await asyncio.sleep(execution_time)

            # Mark as completed
            task_info["status"] = "COMPLETED"
            task_info["completed_at"] = time.time()
            task_info["result"] = (
                f"Task {task_id} completed successfully by {self.agent_id}"
            )

            # Move to completed tasks
            self.completed_tasks[task_id] = task_info
            del self.execution_queue[task_id]

            # Send completion status
            await self._send_execution_status(task_id, "COMPLETED", task_info["result"])

            logger.info(f"Completed execution of task {task_id}")

        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}")

            # Mark as failed
            if task_id in self.execution_queue:
                self.execution_queue[task_id]["status"] = "FAILED"
                self.execution_queue[task_id]["error"] = str(e)
                await self._send_execution_status(
                    task_id, "FAILED", f"Execution failed: {e}"
                )

    async def _send_execution_status(
        self, task_id: str, status: str, result: str = None
    ):
        """Send execution status update"""
        status_data = {
            "task_id": task_id,
            "responder_id": self.agent_id,
            "status": status,
            "counter_offer": None,
            "message": result or f"Task {status.lower()}",
            "timestamp": int(time.time() * 1000),
        }

        await self.send_message("task-responses", "task_response", status_data)
        logger.info(f"Sent {status} status for task {task_id}")

    async def get_execution_queue(self) -> Dict[str, Any]:
        """Get current execution queue"""
        return self.execution_queue

    async def get_completed_tasks(self) -> Dict[str, Any]:
        """Get completed tasks"""
        return self.completed_tasks

    async def get_status(self) -> Dict[str, Any]:
        """Get agent status with executor-specific info"""
        base_status = await super().get_status()
        base_status.update(
            {
                "agent_type": "executor",
                "queued_tasks": len(self.execution_queue),
                "completed_tasks": len(self.completed_tasks),
            }
        )
        return base_status
