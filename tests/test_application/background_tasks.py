import asyncio

from pangloss_core.background_tasks import background_task


'''
# Sample background task

@background_task
async def my_background_task():
    """Runs in background, printing something every five seconds"""
    while True:
        asyncio.sleep(5)
        print("I'm running a background task")
'''