"""stdio tools with per-call host context and a shared application service."""

import os
import uuid

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from .context import ContextResolver
from .errors import TreecerError
from .service import TreeService


class Scope(BaseModel):
    workspace: str | None = Field(None, description="用户实际工作区；服务启动目录不作为依据")
    project: str | None = Field(None, description="手动固定项目 ID 或名称；通常省略")
    source: str | None = Field(None, description="接入来源，如 codex、另一个助手")
    session: str | None = Field(None, description="稳定聊天标识；返回值可用于跨重启接续")


def build_server(home=None, workspace=None, project=None, source="mcp", session=None):
    session = session or os.environ.get("TREECER_SESSION") or uuid.uuid4().hex
    server = FastMCP("Treecer", instructions=(
        "先 context 查看项目和任务。根据用户讨论选择任务，树节点使用自动 ID。"
        "scope 携带工作区与稳定会话；不同聊天使用不同 session。"
        "读取不移动位置，focus 保存接续点。更新携带读取到的 revision。"
    ))

    def resolver(scope):
        scope = scope or Scope()
        return ContextResolver(home, scope.workspace or workspace, scope.source or source, scope.session or session)

    def invoke(method, scope, **kwargs):
        scope = scope or Scope()
        try:
            service = TreeService(resolver(scope), scope.project or project)
            return getattr(service, method)(**kwargs)
        except (TreecerError, OSError) as error:
            import json
            data = error.as_dict() if isinstance(error, TreecerError) else {"error": "IO_ERROR", "message": str(error)}
            raise ToolError(json.dumps(data, ensure_ascii=False)) from error

    @server.tool()
    def context(node_id: str | None = None, tree_id: str | None = None,
                limit: int = 50, offset: int = 0, scope: Scope | None = None) -> dict:
        """查看项目概览或节点正文、祖先路径与一层孩子。首次使用自动发现项目。"""
        return invoke("get_context", scope, node_id=node_id, tree_id=tree_id, limit=limit, offset=offset)

    @server.tool()
    def projects() -> dict:
        """列出此数据目录已登记的项目。"""
        return {"projects": resolver(None).projects()}

    @server.tool()
    def tasks(title: str | None = None, scope: Scope | None = None) -> dict:
        """省略 title 列出任务；提供 title 创建并选中任务。"""
        return invoke("create_task", scope, title=title) if title is not None else invoke("list_tasks", scope)

    @server.tool()
    def trees(title: str | None = None, task: str | None = None,
              project_level: bool = False, note: str = "", scope: Scope | None = None) -> dict:
        """列出当前任务的树；提供 title 创建树并进入根节点。project_level 选择项目级树。"""
        kwargs = {"task": task, "project_level": project_level}
        if title is not None:
            return invoke("create_tree", scope, title=title, note=note, **kwargs)
        return invoke("list_trees", scope, **kwargs)

    @server.tool()
    def add_node(title: str, parent_id: str | None = None, tree_id: str | None = None,
                 note: str = "", scope: Scope | None = None) -> dict:
        """在父节点下创建问题；父节点默认当前位置，ID 自动生成，不改变当前位置。"""
        return invoke("add_node", scope, title=title, parent_id=parent_id, tree_id=tree_id, note=note)

    @server.tool()
    def update_node(node_id: str, revision: int, title: str | None = None,
                    status: str | None = None, note: str | None = None,
                    tree_id: str | None = None, scope: Scope | None = None) -> dict:
        """更新显式提供的字段；note='' 清空正文。冲突返回当前内容，合并后再提交。"""
        return invoke("update_node", scope, node_id=node_id, revision=revision, title=title,
                      status=status, note=note, tree_id=tree_id)

    @server.tool()
    def move_node(node_id: str, new_parent_id: str, revision: int,
                  tree_id: str | None = None, scope: Scope | None = None) -> dict:
        """在同一树内移动整条分支，保留 ID；检查环和修订冲突。"""
        return invoke("move_node", scope, node_id=node_id, new_parent_id=new_parent_id,
                      revision=revision, tree_id=tree_id)

    @server.tool()
    def path(node_id: str | None = None, tree_id: str | None = None,
             scope: Scope | None = None) -> dict:
        """返回根到当前节点的路径，各段保留 ID 与原始标题。"""
        return invoke("get_path", scope, node_id=node_id, tree_id=tree_id)

    @server.tool()
    def parent(node_id: str | None = None, tree_id: str | None = None,
               scope: Scope | None = None) -> dict:
        """返回直接父节点及根到父节点的路径。树根返回空路径。"""
        return invoke("get_parent", scope, node_id=node_id, tree_id=tree_id)

    @server.tool()
    def children(node_id: str | None = None, tree_id: str | None = None,
                 limit: int = 50, offset: int = 0, scope: Scope | None = None) -> dict:
        """只列直接孩子摘要，按创建顺序分页；next_offset 非空时还有结果。"""
        return invoke("show_children", scope, node_id=node_id, tree_id=tree_id, limit=limit, offset=offset)

    @server.tool()
    def find_nodes(query: str, tree_id: str | None = None, limit: int = 50,
                   offset: int = 0, scope: Scope | None = None) -> dict:
        """在项目或指定树中按标题子串查找，返回各匹配项的路径供区分同名。"""
        return invoke("find_nodes", scope, query=query, tree_id=tree_id, limit=limit, offset=offset)

    @server.tool()
    def focus(node_id: str | None = None, tree_id: str | None = None,
              task: str | None = None, project_level: bool = False,
              scope: Scope | None = None) -> dict:
        """保存会话位置。node_id='..' 返回父节点；任务支持 ID 或唯一名称。"""
        return invoke("focus", scope, node_id=node_id, tree_id=tree_id, task=task, project_level=project_level)

    @server.tool()
    def reset_context(scope: Scope | None = None) -> dict:
        """清除本会话项目换绑，下一次调用根据工作区重新发现；保留讨论内容。"""
        return resolver(scope).reset()

    return server


def serve(**kwargs):
    build_server(**kwargs).run(transport="stdio")
