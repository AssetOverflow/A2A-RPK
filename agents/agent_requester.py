import uuid
import time
import logging
from typing import Dict, Any
from agent_base import AgentBase

logger = logging.getLogger(__name__)


class RequesterAgent(AgentBase):
    """Agent that requests tasks from other agents"""

    def __init__(self, agent_id: str):
        super().__init__(agent_id)
        self.pending_requests: Dict[str, Dict] = {}

    async def _subscribe_to_topics(self):
        """Subscribe to task responses and negotiation messages"""
        topics = ["task-responses", "negotiations"]
        self.consumer.subscribe(topics)
        logger.info(f"RequesterAgent {self.agent_id} subscribed to {topics}")

    async def _process_message(self, msg):
        """Process incoming messages"""
        topic = msg.topic

        try:
            if topic == "task-responses":
                await self._handle_task_response(msg)
            elif topic == "negotiations":
                await self._handle_negotiation_message(msg)
        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")

    async def _handle_task_response(self, msg):
        """Handle task response messages"""
        try:
            response = self.deserialize_message("task_response", msg.value)

            task_id = response["task_id"]

            if task_id in self.pending_requests:
                self.pending_requests[task_id]["responses"].append(response)
                logger.info(
                    f"Received response for task {task_id} from {response['responder_id']}"
                )

                # Handle based on status
                if response["status"] == "ACCEPTED":
                    logger.info(
                        f"Task {task_id} accepted by {response['responder_id']}"
                    )
                elif response["status"] == "REJECTED":
                    logger.info(
                        f"Task {task_id} rejected by {response['responder_id']}"
                    )
                elif response["status"] == "NEGOTIATING":
                    logger.info(
                        f"Task {task_id} entering negotiation with {response['responder_id']}"
                    )

        except Exception as e:
            logger.error(f"Error handling task response: {e}")

    async def _handle_negotiation_message(self, msg):
        """Handle negotiation messages"""
        try:
            negotiation = self.deserialize_message("negotiation", msg.value)

            if negotiation["receiver_id"] == self.agent_id:
                task_id = negotiation["task_id"]
                logger.info(
                    f"Received negotiation for task {task_id} from {negotiation['sender_id']}"
                )

                # Auto-respond to negotiation (simple logic)
                if (
                    negotiation["offer"] and negotiation["offer"] <= 100.0
                ):  # Accept reasonable offers
                    await self._send_negotiation_response(
                        task_id, negotiation["sender_id"], True, negotiation["offer"]
                    )
                else:
                    # Counter-offer
                    counter_offer = (
                        negotiation["offer"] * 0.8 if negotiation["offer"] else 50.0
                    )
                    await self._send_negotiation_response(
                        task_id, negotiation["sender_id"], False, counter_offer
                    )

        except Exception as e:
            logger.error(f"Error handling negotiation message: {e}")

    async def request_task(self, description: str, proposed_cost: float = None) -> str:
        """Request a new task from available agents"""
        task_id = str(uuid.uuid4())

        request_data = {
            "task_id": task_id,
            "requester_id": self.agent_id,
            "description": description,
            "proposed_cost": proposed_cost,
            "priority": 1,
            "timestamp": int(time.time() * 1000),
        }

        # Store pending request
        self.pending_requests[task_id] = {
            "request": request_data,
            "responses": [],
            "status": "PENDING",
        }

        # Send to task requests topic
        await self.send_message("task-requests", "task_request", request_data)

        logger.info(f"Requested task {task_id}: {description}")
        return task_id

    async def _send_negotiation_response(
        self, task_id: str, receiver_id: str, approved: bool, offer: float
    ):
        """Send negotiation response"""
        negotiation_data = {
            "task_id": task_id,
            "sender_id": self.agent_id,
            "receiver_id": receiver_id,
            "negotiation_round": 1,  # Simplified
            "offer": offer,
            "approved": approved,
            "message": "Auto-negotiation response",
            "timestamp": int(time.time() * 1000),
        }

        await self.send_message("negotiations", "negotiation", negotiation_data)

    async def get_pending_requests(self) -> Dict[str, Any]:
        """Get all pending requests"""
        return self.pending_requests

    async def get_status(self) -> Dict[str, Any]:
        """Get agent status with request-specific info"""
        base_status = await super().get_status()
        base_status.update(
            {"agent_type": "requester", "pending_requests": len(self.pending_requests)}
        )
        return base_status
