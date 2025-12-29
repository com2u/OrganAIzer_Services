from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def root():
    return {"message": "OrganAIzer Service API"}

@router.get("/health")
async def health():
    return {"status": "ok"}
