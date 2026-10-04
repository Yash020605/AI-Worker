"""
Start the main AI Worker API server on port 8000.
Run: python run_api.py
"""
import uvicorn
from agent.config import config

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=config.APP_HOST,
        port=config.APP_PORT,
        reload=config.APP_DEBUG,
        log_level=config.LOG_LEVEL.lower(),
    )
