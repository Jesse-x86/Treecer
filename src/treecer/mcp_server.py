"""Path-based stdio tools. Each mutation explicitly carries its sudo override."""

import json
import os
import uuid

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from .context import ContextResolver
from .errors import TreecerError
from .service import TreeService


class Scope(BaseModel):
    workspace: str | None = Field(
        None, description="用户实际工作区；服务启动目录不作为依据"
    )
    project: str | None = Field(None, description="手动固定项目名称；通常省略")
    source: str | None = Field(None, description="接入来源，如 codex")
    session: str | None = Field(
        None, description="稳定聊天标识；返回值可用于跨重启接续"
    )


def build_server(home=None, workspace=None, project=None, source="mcp", session=None):
    session = session or os.environ.get("TREECER_SESSION") or uuid.uuid4().hex
    server = FastMCP(
        "Treecer",
        instructions=(
            "用名称和路径操作讨论。先 context 查看当前位置；tasks 创建任务，use_task 选择任务。"
            "~ 表示当前任务根，/项目/任务/节点 为绝对路径，支持相对路径、.、..。"
            "普通读取和写入保留会话位置，focus 明确移动位置。prompt 始终显示真实位置。"
            "跨任务查看直接允许，跨任务写入必须显式 sudo=true；它只对本次请求生效。"
            "读取后携带 revision 更新，冲突时合并 current 内容。每个聊天用独立稳定 scope.session。"
        ),
    )

    def resolver(scope):
        scope = scope or Scope()
        return ContextResolver(
            home,
            scope.workspace or workspace,
            scope.source or source,
            scope.session or session,
        )

    def invoke(method, scope, **kwargs):
        scope = scope or Scope()
        try:
            return getattr(
                TreeService(resolver(scope), scope.project or project), method
            )(**kwargs)
        except (TreecerError, OSError) as error:
            data = (
                error.as_dict()
                if isinstance(error, TreecerError)
                else {"error": "IO_ERROR", "message": str(error)}
            )
            raise ToolError(json.dumps(data, ensure_ascii=False)) from error

    @server.tool()
    def context(
        path: str | None = None,
        limit: int = 50,
        offset: int = 0,
        scope: Scope | None = None,
    ) -> dict:
        """读取当前或指定路径的正文、祖先和一层孩子。跨任务读取直接允许，保留当前位置。"""
        return invoke("get_context", scope, path=path, limit=limit, offset=offset)

    @server.tool()
    def projects() -> dict:
        """列出已登记项目的名称和路径。"""
        return {"projects": resolver(None).projects()}

    @server.tool()
    def tasks(title: str | None = None, scope: Scope | None = None) -> dict:
        """省略 title 列出当前项目的任务；提供 title 创建并选中新任务的 ~ 根。"""
        return (
            invoke("create_task", scope, title=title)
            if title is not None
            else invoke("list_tasks", scope)
        )

    @server.tool()
    def use_task(title: str, scope: Scope | None = None) -> dict:
        """按唯一任务名称改变当前任务绑定，并恢复该任务保存的位置。"""
        return invoke("use_task", scope, title=title)

    @server.tool()
    def add_node(
        title: str,
        parent: str | None = None,
        note: str = "",
        sudo: bool = False,
        scope: Scope | None = None,
    ) -> dict:
        """新增孩子，parent 默认当前位置。同父名称唯一；跨任务写入显式 sudo=true。"""
        return invoke(
            "add_node", scope, title=title, parent=parent, note=note, sudo=sudo
        )

    @server.tool()
    def update_node(
        path: str,
        revision: int,
        title: str | None = None,
        status: str | None = None,
        note: str | None = None,
        sudo: bool = False,
        scope: Scope | None = None,
    ) -> dict:
        """按路径和读取到的 revision 更新提供字段。note='' 清空正文；跨任务显式 sudo=true。"""
        return invoke(
            "update_node",
            scope,
            path=path,
            revision=revision,
            title=title,
            status=status,
            note=note,
            sudo=sudo,
        )

    @server.tool()
    def move_node(
        path: str,
        new_parent: str,
        revision: int,
        sudo: bool = False,
        scope: Scope | None = None,
    ) -> dict:
        """把分支移动到父路径，保留内部身份与会话跟随。涉及其他任务时显式 sudo=true。"""
        return invoke(
            "move_node",
            scope,
            path=path,
            new_parent=new_parent,
            revision=revision,
            sudo=sudo,
        )

    @server.tool()
    def path(path: str | None = None, scope: Scope | None = None) -> dict:
        """读取路径和祖先，跨任务查看直接允许。"""
        return invoke("get_path", scope, path=path)

    @server.tool()
    def parent(path: str | None = None, scope: Scope | None = None) -> dict:
        """读取直接父位置；任务根的父位置为项目，绝对根的父位置为空。"""
        return invoke("get_parent", scope, path=path)

    @server.tool()
    def children(
        path: str | None = None,
        limit: int = 50,
        offset: int = 0,
        scope: Scope | None = None,
    ) -> dict:
        """只列直接孩子摘要；next_offset 非空时有下一页。支持跨任务读取。"""
        return invoke("show_children", scope, path=path, limit=limit, offset=offset)

    @server.tool()
    def find_nodes(
        query: str,
        path: str | None = None,
        limit: int = 50,
        offset: int = 0,
        scope: Scope | None = None,
    ) -> dict:
        """在路径下按标题子串查找；默认当前任务，跨任务搜索直接允许。"""
        return invoke(
            "find_nodes", scope, query=query, path=path, limit=limit, offset=offset
        )

    @server.tool()
    def focus(path: str = "~", scope: Scope | None = None) -> dict:
        """明确保存讨论位置。~ 返回任务根；跨任务位置用绝对路径显示，任务绑定保留。"""
        return invoke("focus", scope, path=path)

    @server.tool()
    def reset_context(scope: Scope | None = None) -> dict:
        """清除当前会话的项目固定关联，保留讨论内容与位置。"""
        return resolver(scope).reset()

    return server


def serve(**kwargs):
    build_server(**kwargs).run(transport="stdio")
