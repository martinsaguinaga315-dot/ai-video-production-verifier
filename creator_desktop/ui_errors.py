from __future__ import annotations

import socket
from urllib.error import HTTPError, URLError

from verification_service import (
    InputFileNotFoundError,
    InputJsonError,
    InputSchemaError,
    ReportWriteError,
    SemanticVerificationError,
)


def friendly_error(error: Exception) -> str:
    """Map implementation errors to short Chinese user-facing messages."""
    if isinstance(error, InputFileNotFoundError):
        return "找不到文件或文件无法读取，请重新选择。"
    if isinstance(error, InputJsonError):
        return "JSON格式错误，请检查文件内容。"
    if isinstance(error, InputSchemaError):
        return "JSON结构不符合facts或导演方案的要求。"
    if isinstance(error, ReportWriteError):
        return "报告导出失败，请检查保存位置和权限。"
    if isinstance(error, SemanticVerificationError):
        messages = {
            "api_key_missing": "请先在API设置中保存DeepSeek API Key。",
            "api_key_invalid": "API Key无效。",
            "connection_failed": "无法连接DeepSeek，请检查网络。",
            "timeout": "请求超时，请稍后重试。",
            "rate_limited": "请求频率过高，请稍后重试。",
            "insufficient_permission": "账户余额不足或没有访问权限。",
            "service_unavailable": "DeepSeek服务暂时不可用。",
        }
        return messages.get(error.code, "语义审计失败，请检查API Key和网络后重试。")
    if isinstance(error, TimeoutError):
        return "请求超时，请稍后重试。"
    if isinstance(error, (socket.timeout, URLError, ConnectionError)):
        return "无法连接DeepSeek，请检查网络。"
    if isinstance(error, HTTPError):
        if error.code == 401:
            return "API Key无效。"
        if error.code == 429:
            return "请求频率过高，请稍后重试。"
        if error.code in (402, 403):
            return "账户余额不足或没有访问权限。"
        if error.code >= 500:
            return "DeepSeek服务暂时不可用。"
    return "操作失败，请稍后重试。"
