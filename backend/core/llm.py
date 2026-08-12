import os
from langchain_google_genai import ChatGoogleGenerativeAI
from fastapi import HTTPException

def get_llm():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GOOGLE_API_KEY environment variable is not set. The autonomous agents require this to function."
        )
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=api_key,
        temperature=0.1
    )
