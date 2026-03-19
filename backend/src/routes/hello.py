from fastapi import APIRouter

router = APIRouter(tags=["hello"])


@router.get("/hello")
async def get_hello():
    return {"message": "Hello from FastAPI"}
