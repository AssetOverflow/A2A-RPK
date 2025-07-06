import time
import logging
from typing import Dict, Any
from agent_base import AgentBase

logger = logging.getLogger(__name__)


class ProviderAgent(AgentBase):
    """Agent that provides/accepts tasks from requesters"""

    def __init__(self, agent_id: str):
        super().__init__(agent_id)
        self.capabilities = ["data_processing", "analysis", "reporting"]
        self.max_cost = 150.0
        self.active_negotiations: Dict[str, Dict] = {}

    async def _subscribe_to_topics(self):
        """Subscribe to task requests and negotiation messages"""
        topics = ["task-requests", "negotiations"]
        self.consumer.subscribe(topics)
        logger.info(f"ProviderAgent {self.agent_id} subscribed to {topics}")

    async def _process_message(self, msg):
        """Process incoming messages"""
        topic = msg.topic

        try:
            if topic == "task-requests":
                await self._handle_task_request(msg)
            elif topic == "negotiations":
                await self._handle_negotiation_message(msg)
        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")

    async def _handle_task_request(self, msg):
        """Handle incoming task requests"""
        try:
            request = self.deserialize_message("task_request", msg.value)

            task_id = request["task_id"]
            logger.info(
                f"Received task request {task_id} from {request['requester_id']}"
            )

            # Evaluate if we can handle this task
            can_handle = await self._can_handle_task(request)

            if can_handle:
                # Send positive response
                await self._send_task_response(request, "ACCEPTED")
            else:
                # Check if we want to negotiate
                if request.get("proposed_cost", 0) < self.max_cost:
                    await self._send_task_response(request, "NEGOTIATING")
                    await self._start_negotiation(request)
                else:
                    await self._send_task_response(request, "REJECTED", "Cost too high")

        except Exception as e:
            logger.error(f"Error handling task request: {e}")

    async def _handle_negotiation_message(self, msg):
        """Handle negotiation messages"""
        try:
            negotiation = self.deserialize_message("negotiation", msg.value)

            if negotiation["receiver_id"] == self.agent_id:
                task_id = negotiation["task_id"]
                logger.info(f"Received negotiation for task {task_id}")

                if negotiation["approved"]:
                    # Negotiation approved, accept the task
                    await self._accept_negotiated_task(task_id, negotiation["offer"])
                else:
                    # Counter-negotiation, evaluate counter-offer
                    if negotiation["offer"] and negotiation["offer"] >= 30.0:
                        # Accept counter-offer
                        await self._send_negotiation_response(
                            task_id,
                            negotiation["sender_id"],
                            True,
                            negotiation["offer"],
                        )
                    else:
                        # Reject
                        await self._send_negotiation_response(
                            task_id, negotiation["sender_id"], False, None
                        )

        except Exception as e:
            logger.error(f"Error handling negotiation: {e}")

    async def _can_handle_task(self, request: Dict[str, Any]) -> bool:
        """Determine if we can handle this task"""
        # Simple capability check based on description keywords
        description = request["description"].lower()

        for capability in self.capabilities:
            if capability.replace("_", " ") in description:
                return True

        return False

    async def _send_task_response(
        self, request: Dict[str, Any], status: str, message: str = None
    ):
        """Send response to task request"""
        response_data = {
            "task_id": request["task_id"],
            "responder_id": self.agent_id,
            "status": status,
            "counter_offer": None,
            "message": message,
            "timestamp": int(time.time() * 1000),
        }

        if status == "NEGOTIATING" and request.get("proposed_cost"):
            # Suggest a counter-offer
            response_data["counter_offer"] = min(
                request["proposed_cost"] * 1.2, self.max_cost
            )

        await self.send_message("task-responses", "task_response", response_data)
        logger.info(f"Sent {status} response for task {request['task_id']}")

    async def _start_negotiation(self, request: Dict[str, Any]):
        """Start negotiation for a task"""
        task_id = request["task_id"]

        negotiation_data = {
            "task_id": task_id,
            "sender_id": self.agent_id,
            "receiver_id": request["requester_id"],
            "negotiation_round": 1,
            "offer": min(request.get("proposed_cost", 0) * 1.2, self.max_cost),
            "approved": False,
            "message": "Starting negotiation",
            "timestamp": int(time.time() * 1000),
        }

        self.active_negotiations[task_id] = {
            "request": request,
            "round": 1,
            "status": "ACTIVE",
        }

        await self.send_message("negotiations", "negotiation", negotiation_data)

    async def _send_negotiation_response(
        self, task_id: str, receiver_id: str, approved: bool, offer: float
    ):
        """Send negotiation response"""
        negotiation_data = {
            "task_id": task_id,
            "sender_id": self.agent_id,
            "receiver_id": receiver_id,
            "negotiation_round": 2,  # Simplified
            "offer": offer,
            "approved": approved,
            "message": "Negotiation response",
            "timestamp": int(time.time() * 1000),
        }

        await self.send_message("negotiations", "negotiation", negotiation_data)

    async def _accept_negotiated_task(self, task_id: str, final_cost: float):
        """Accept a task after successful negotiation"""
        if task_id in self.active_negotiations:
            request = self.active_negotiations[task_id]["request"]

            # Send final acceptance
            response_data = {
                "task_id": task_id,
                "responder_id": self.agent_id,
                "status": "ACCEPTED",
                "counter_offer": final_cost,
                "message": f"Task accepted at ${final_cost}",
                "timestamp": int(time.time() * 1000),
            }

            await self.send_message("task-responses", "task_response", response_data)

            # Move to tasks
            self.tasks[task_id] = {
                "request": request,
                "cost": final_cost,
                "status": "ACCEPTED",
            }

            del self.active_negotiations[task_id]
            logger.info(f"Accepted task {task_id} at ${final_cost}")

    async def get_status(self) -> Dict[str, Any]:
        """Get agent status with provider-specific info"""
        base_status = await super().get_status()
        base_status.update(
            {
                "agent_type": "provider",
                "capabilities": self.capabilities,
                "max_cost": self.max_cost,
                "active_negotiations": len(self.active_negotiations),
            }
        )
        return base_status
