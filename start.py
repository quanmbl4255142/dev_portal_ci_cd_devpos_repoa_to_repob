"""
Script đơn giản để chạy Dev Portal
"""
import asyncio
import logging
import uvicorn
from auto_sync_service import start_auto_sync, stop_auto_sync

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Main function"""
    try:
        print("🚀 Starting Django Dev Portal...")
        print("📊 Dashboard: http://localhost:8080/static/dashboard.html")
        print("📚 API Docs: http://localhost:8080/docs")
        print("🔄 Auto sync will start automatically")
        print("=" * 50)
        
        # Start auto sync in background
        sync_task = asyncio.create_task(start_auto_sync())
        
        # Start FastAPI server
        config = uvicorn.Config(
            "main:app",
            host="0.0.0.0",
            port=8080,
            log_level="info",
            reload=False
        )
        server = uvicorn.Server(config)
        
        try:
            await server.serve()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        finally:
            # Stop auto sync
            sync_task.cancel()
            await stop_auto_sync()
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
