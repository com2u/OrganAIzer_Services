from fastapi import APIRouter
from pydantic import BaseModel
from services import llm_service

router = APIRouter()

class LLMRequest(BaseModel):
    prompt: str
    model: str = "openrouter/auto"

@router.post("/llm")
def get_llm_response(request: LLMRequest):
    response = llm_service.get_llm_response(request.prompt, request.model)
    return {"response": response}
