from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import psutil
import redis
from web3 import Web3
import os

app = FastAPI()

def check_web3_connection():
    try:
        w3 = Web3(Web3.HTTPProvider(os.getenv('WEB3_PROVIDER_URI', 'http://geth:8545')))
        return w3.is_connected()
    except Exception:
        return False

def check_redis_connection():
    try:
        r = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0
        )
        return r.ping()
    except Exception:
        return False

@app.get("/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "web3_connected": check_web3_connection(),
        "redis_connected": check_redis_connection(),
        "memory_usage": psutil.Process().memory_info().rss / 1024 / 1024,  # MB
        "cpu_percent": psutil.Process().cpu_percent()
    }
    
    if not all([health_status["web3_connected"], health_status["redis_connected"]]):
        raise HTTPException(status_code=503, detail="Service dependencies not available")
    
    return JSONResponse(content=health_status)
