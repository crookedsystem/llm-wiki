from pydantic import BaseModel, Field

JsonSchema = dict[str, object]


class ToolResponse(BaseModel):
    name: str = Field(description="MCP tool 이름")
    description: str | None = Field(description="MCP tool이 수행하는 작업 설명")
    inputSchema: JsonSchema = Field(description="MCP tool 입력 JSON schema")
    outputSchema: JsonSchema | None = Field(description="MCP tool 출력 JSON schema")
