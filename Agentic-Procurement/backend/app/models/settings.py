from pydantic import BaseModel, Field

class Settings(BaseModel):
    gemini_key: str = Field(default="", description="Google Gemini API Key")
    claude_key: str = Field(default="", description="Anthropic Claude API Key")
    buyer_model: str = Field(default="gemini-1.5-flash", description="Gemini model to use for Buyer Agent")
    supplier_model: str = Field(default="claude-3-5-sonnet-20240620", description="Claude model to use for Supplier Agent")
