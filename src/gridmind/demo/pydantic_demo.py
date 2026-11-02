"""学习示例：Pydantic v2 完整功能速览

覆盖：
- BaseModel / Field 约束
- 嵌套模型、Literal、Optional、默认工厂
- field_validator / model_validator
- computed_field
- 别名与序列化（model_dump / model_validate）
- ConfigDict（额外字段、字符串裁剪）
- Annotated + 自定义校验
- JSON Schema 导出

运行::

    uv run python -m gridmind.demo pydantic
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)

from gridmind.demo._common import banner


# ---------- 基础枚举 / 自定义校验 ----------


class AlarmLevel(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


def _non_blank(v: str) -> str:
    if not v.strip():
        raise ValueError("不能为空字符串")
    return v.strip()


NonBlankStr = Annotated[str, AfterValidator(_non_blank)]


# ---------- 嵌套与主模型 ----------


class DeviceRef(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    device_id: str = Field(pattern=r"^DEV-\d{3}$", description="设备编号")
    station: str = Field(min_length=1, max_length=64)


class ChatbiQuery(BaseModel):
    """模拟一次问数请求的完整校验。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",  # 禁止未知字段
        populate_by_name=True,
    )

    question: NonBlankStr = Field(..., min_length=1, max_length=500)
    intent: Literal["rag", "nl2sql", "mcp", "hybrid"] = "nl2sql"
    level: AlarmLevel | None = None
    limit: int = Field(default=10, ge=1, le=100)
    device: DeviceRef | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    # 别名：JSON 里可用 userId，代码里用 user_id
    user_id: str = Field(default="demo-user", alias="userId", min_length=1)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        return sorted({t.strip().lower() for t in v if t.strip()})

    @model_validator(mode="after")
    def check_mcp_needs_device(self) -> ChatbiQuery:
        if self.intent == "mcp" and self.device is None:
            raise ValueError("intent=mcp 时必须提供 device")
        if self.intent == "hybrid" and self.limit < 3:
            raise ValueError("hybrid 建议 limit>=3")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def summary(self) -> str:
        device = self.device.device_id if self.device else "-"
        return f"{self.intent}/{self.limit}/device={device}"


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    banner("Pydantic v2 完整功能 demo")

    # 1) 成功校验 + 计算字段 + 序列化
    section("1) 合法数据 → 模型 / dump / alias")
    ok = ChatbiQuery.model_validate(
        {
            "question": "  各区域告警数量？  ",
            "intent": "nl2sql",
            "level": "warning",
            "limit": 5,
            "tags": [" Grid ", "Alarm", "grid"],
            "userId": "u-1001",
        }
    )
    print("summary      =", ok.summary)
    print("tags         =", ok.tags)
    print("dump(by_alias) =", ok.model_dump(by_alias=True))
    print("json         =", ok.model_dump_json(by_alias=True))

    # 2) 嵌套模型
    section("2) 嵌套 DeviceRef")
    nested = ChatbiQuery(
        question="设备状态",
        intent="mcp",
        device=DeviceRef(device_id="DEV-001", station=" 华东变电站 "),
    )
    print(nested.model_dump())

    # 3) Field 约束失败
    section("3) Field 约束失败（limit>100）")
    try:
        ChatbiQuery(question="x", limit=999)
    except ValidationError as exc:
        print(exc.errors()[0])

    # 4) pattern 失败
    section("4) 正则失败（device_id）")
    try:
        DeviceRef(device_id="device1", station="S1")
    except ValidationError as exc:
        print(exc.errors()[0]["msg"])

    # 5) extra=forbid
    section("5) 禁止多余字段")
    try:
        ChatbiQuery.model_validate({"question": "hi", "hack": True})
    except ValidationError as exc:
        print(exc.errors()[0]["type"], exc.errors()[0]["msg"])

    # 6) model_validator 跨字段
    section("6) model_validator：mcp 缺 device")
    try:
        ChatbiQuery(question="查设备", intent="mcp")
    except ValidationError as exc:
        print(exc.errors()[0]["msg"])

    # 7) Annotated 自定义校验
    section("7) Annotated 去空白/拒空串")
    try:
        ChatbiQuery(question="   ")
    except ValidationError as exc:
        print(exc.errors()[0]["msg"])

    # 8) 枚举
    section("8) Enum")
    print(AlarmLevel.critical, AlarmLevel("warning"))

    # 9) JSON Schema（可给前端/OpenAPI 用）
    section("9) JSON Schema 片段")
    schema: dict[str, Any] = ChatbiQuery.model_json_schema()
    print("title =", schema.get("title"))
    print("required =", schema.get("required"))
    print("properties.question =", schema["properties"]["question"])

    # 10) 与 Settings 的分工提示
    section("10) 和 pydantic-settings 的分工")
    print("BaseModel  → 请求/响应/领域对象校验")
    print("BaseSettings → 环境变量与运行配置")
    print("FastAPI 入参本质就是 BaseModel 校验。")


if __name__ == "__main__":
    main()
