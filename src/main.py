import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from src.config import TELEGRAM_TOKEN
from src.agent import StupidAgent
from src.scheduler import TaskScheduler
from src.skills import SkillLoader

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Multi-session support: one agent per user (shared memory manager)
# In production, this should use a proper session store (Redis, etc.)
agents = {}

# Initialize scheduler and skills
scheduler = TaskScheduler()
skill_loader = SkillLoader()

def get_or_create_agent(chat_id: str) -> StupidAgent:
    """Get existing agent for user or create new one"""
    if chat_id not in agents:
        agents[chat_id] = StupidAgent()
        logging.info(f"Created new agent for chat {chat_id}")
    return agents[chat_id]

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(
        "Hello! I am StupidClaw. I am cheap, strict, and tool-reliant.\n\n"
        "I have memory across sessions and can help with:\n"
        "- Research (web search + analysis)\n"
        "- Code (file operations + shell)\n"
        "- Memory (storing and recalling facts about you)\n"
        "- HTTP requests (via http tool)\n"
        "- Docker operations (via docker tool)\n\n"
        "Commands:\n"
        "/cron list — Show scheduled jobs\n"
        "/cron remove <job_id> — Remove a cron job\n\n"
        "Send me a task!"
    )

@dp.message(lambda msg: msg.text and msg.text.startswith("/cron"))
async def cron_handler(message: Message) -> None:
    """Handle cron commands"""
    try:
        parts = message.text.split()
        
        if len(parts) < 2:
            await message.answer("Usage: /cron list | /cron remove <job_id>")
            return
        
        cmd = parts[1].lower()
        
        if cmd == "list":
            tasks = scheduler.list_tasks()
            if not tasks:
                await message.answer("No scheduled jobs")
                return
            
            response = "📅 Scheduled Jobs:\n\n"
            for job_id, info in tasks.items():
                response += f"• {job_id}\n"
                response += f"  Type: {info['type']}\n"
                response += f"  Schedule: {info['schedule']}\n"
                response += f"  Next run: {info['next_run']}\n\n"
            
            await message.answer(response)
            
        elif cmd == "remove":
            if len(parts) < 3:
                await message.answer("Usage: /cron remove <job_id>")
                return
            
            job_id = parts[2]
            if scheduler.remove_task(job_id):
                await message.answer(f"✅ Removed job '{job_id}'")
            else:
                await message.answer(f"❌ Job '{job_id}' not found")
        
        else:
            await message.answer(f"Unknown cron command: {cmd}\nAvailable: list, remove")
            
    except Exception as e:
        logging.error(f"Error handling cron command: {e}")
        await message.answer(f"Error: {e}")

@dp.message()
async def echo_handler(message: Message) -> None:
    try:
        # Send a "thinking" action
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # Get or create agent for this user
        chat_id = str(message.chat.id)
        agent = get_or_create_agent(chat_id)
        
        # Run the agent with chat_id for memory tracking
        response = agent.run(message.text, chat_id=chat_id)
        
        # Safety check: ensure response is a string
        if not response or not isinstance(response, str):
            response = "I encountered an issue processing your request."
        
        await message.answer(response)
    except Exception as e:
        logging.error(f"Error handling message: {e}")
        await message.answer(f"Error: {e}")

async def on_startup():
    """Run on bot startup"""
    logging.info(f"Loaded {len(skill_loader.list_skills())} skills: {', '.join(skill_loader.list_skills())}")
    
    # Start scheduler
    scheduler.start()
    
    # Example: Add daily memory consolidation at midnight
    # scheduler.add_daily_task(
    #     "memory_consolidation",
    #     lambda: daily_memory_consolidation(agent.memory, list(agents.keys())),
    #     hour=0,
    #     minute=0
    # )

async def on_shutdown():
    """Run on bot shutdown"""
    scheduler.stop()
    logging.info("Scheduler stopped, bot shutdown complete")

async def main() -> None:
    await on_startup()
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN not set in .env")
        sys.exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
