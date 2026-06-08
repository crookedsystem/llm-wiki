from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="서버 상태")
    mcp_path: str = Field(description="MCP streamable HTTP mount path")
