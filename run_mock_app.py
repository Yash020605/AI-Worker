"""
Start the simulated company application on port 8001.
Run: python run_mock_app.py
"""
import uvicorn
from agent.config import config

if __name__ == "__main__":
    uvicorn.run(
        "mock_app.app:app",
        host=config.MOCK_APP_HOST if hasattr(config, 'MOCK_APP_HOST') else "0.0.0.0",
        port=config.MOCK_APP_PORT,
        reload=config.APP_DEBUG,
        log_level="info",
    )
