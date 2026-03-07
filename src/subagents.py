"""
Sub-Agent Spawning — Simplified decomposition for multi-step tasks
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class SubAgentManager:
    """Manages sub-agent spawning for complex multi-step tasks"""
    
    def __init__(self, agent):
        self.agent = agent
        self.max_subtasks = 5
    
    def should_decompose(self, plan: dict) -> bool:
        """
        Rule-based: decompose if plan has >3 steps
        """
        steps = plan.get("steps", [])
        return len(steps) > 3
    
    def decompose_task(self, goal: str, plan: dict) -> List[str]:
        """
        Break a complex goal into sub-tasks based on the plan
        """
        steps = plan.get("steps", [])
        
        # Simple strategy: each step becomes a sub-task
        subtasks = []
        for step in steps[:self.max_subtasks]:
            desc = step.get("description", "")
            tool = step.get("tool", "")
            if desc:
                subtasks.append(f"{desc} (using {tool})")
        
        return subtasks
    
    def run_subtask(self, subtask: str, chat_id: str) -> str:
        """
        Execute a single sub-task using the main agent
        """
        logger.info(f"Running subtask: {subtask[:50]}...")
        try:
            # Run as a separate agent call
            result = self.agent.run(subtask, chat_id=chat_id)
            logger.info(f"Subtask complete: {result[:50]}...")
            return result
        except Exception as e:
            logger.error(f"Subtask failed: {e}")
            return f"Error: {e}"
    
    def synthesize_results(self, goal: str, subtask_results: List[Dict]) -> str:
        """
        Aggregate sub-task results into final answer
        """
        # Build synthesis prompt
        synthesis_prompt = f"Original goal: {goal}\n\nSub-task results:\n"
        for i, result in enumerate(subtask_results, 1):
            task = result['task']
            output = result['output']
            synthesis_prompt += f"\n{i}. {task}\nResult: {output[:200]}\n"
        
        synthesis_prompt += "\nSynthesize these results into a coherent final answer."
        
        # Use LLM to synthesize
        final_answer = self.agent._llm([
            {"role": "system", "content": "You are a synthesis expert. Combine the sub-task results into a clear, complete answer."},
            {"role": "user", "content": synthesis_prompt}
        ])
        
        return final_answer
    
    def run_with_decomposition(self, goal: str, chat_id: str) -> str:
        """
        Main entry point: check if decomposition needed, run subtasks, synthesize
        """
        # Get plan
        plan = self.agent._plan(goal)
        
        # Check if decomposition needed
        if not self.should_decompose(plan):
            logger.info("Task simple enough, no decomposition needed")
            return None  # Signal to use normal flow
        
        logger.info("Complex task detected, decomposing into sub-agents...")
        
        # Decompose
        subtasks = self.decompose_task(goal, plan)
        
        # Run each subtask
        results = []
        for subtask in subtasks:
            output = self.run_subtask(subtask, chat_id)
            results.append({
                "task": subtask,
                "output": output
            })
        
        # Synthesize
        final_answer = self.synthesize_results(goal, results)
        
        logger.info("Sub-agent decomposition complete")
        return final_answer


class SelfModifier:
    """
    Templated self-modification — agent can update memory files
    """
    
    def __init__(self, memory_manager):
        self.memory = memory_manager
    
    def update_memory_fact(self, fact: str, chat_id: str = "default"):
        """Add a fact to MEMORY.md"""
        logger.info(f"Self-modifying: Adding fact to MEMORY.md")
        self.memory.procedural.update_memory(fact)
        self.memory.episodic.log_event("self_modification", {
            "type": "memory_update",
            "fact": fact,
            "chat_id": chat_id
        })
    
    def update_user_preference(self, preference: str, chat_id: str = "default"):
        """Add user preference to USER.md"""
        logger.info(f"Self-modifying: Adding preference to USER.md")
        self.memory.procedural.update_user_info(preference)
        self.memory.episodic.log_event("self_modification", {
            "type": "user_preference_update",
            "preference": preference,
            "chat_id": chat_id
        })
    
    def extract_and_store_facts(self, message: str, response: str, chat_id: str):
        """
        Analyze conversation and extract facts to store
        Uses templates to avoid free-form editing
        """
        # Pattern 1: "My name is X"
        if "my name is" in message.lower():
            import re
            match = re.search(r"my name is (\w+)", message.lower())
            if match:
                name = match.group(1).title()
                self.update_user_preference(f"Name: {name}", chat_id)
        
        # Pattern 2: "I live in X"
        if "i live in" in message.lower():
            import re
            match = re.search(r"i live in ([\w\s]+)", message.lower())
            if match:
                location = match.group(1).title()
                self.update_user_preference(f"Location: {location}", chat_id)
        
        # Pattern 3: "Remember that..."
        if "remember that" in message.lower():
            # Extract everything after "remember that"
            fact = message.lower().split("remember that", 1)[1].strip()
            self.update_memory_fact(fact, chat_id)
