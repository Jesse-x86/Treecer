# Discussion workflow

## Start from the current location

Call `treecer context show --json` or MCP `context` to inspect the project, task, ancestor path, current content, and direct children. Check that they match the discussion; read ancestors when their context is needed.

A new session starts at the project overview. Select an existing task when the user refers to it; create a task for new work. Project-level trees can hold questions that do not yet belong to a task.

## Record useful questions and decisions

Store questions worth returning to, including their purpose and enough context to continue. For example:

```text
Purpose: How can an assistant resume its discussion position?
User decided: Separate projects from tasks; persist session positions.
Assistant suggestion: Identify positions by source and session.
Open question: How does the host provide a stable session identity?
Next step: Exercise a real client restart.
```

Use the fields that help. Distinguish user decisions, assistant proposals, and open questions. Record missing evidence explicitly. Keep remaining questions when only part of a node is resolved.

## Explore and defer

Use `node add` or MCP `add_node` to create a child for a question worth exploring. The tool assigns its ID. Creation preserves the current position; call `focus` when you move into the new question.

For a branch to revisit later, record its question, context, and return condition. Set its status to `暂放` (deferred), then continue the original discussion. IDs and paths distinguish duplicate titles.

## Conclude and return

When a question is settled, update its conclusions and identify which part of the parent it resolves:

```text
treecer node get N27 --json
treecer node update N27 --revision 3 --status 已解决 --note "User decided: ..."
treecer parent
treecer focus ..
treecer children
```

Use the actual returned ID and revision. `parent` reads the parent and path; `focus ..` saves the position at the parent. Check the parent's remaining questions and select an open sibling branch. The user can change the discussion order at any time.

Reopen questions with `讨论中` (in discussion). When a new decision replaces an old proposal, update the effective conclusion and retain important reasons when useful.

## Update and collaborate

Update after important decisions, branching, direction changes, or the end of a discussion round. Keep conversation focused on the substantive questions.

Use the returned `revision` when updating. For `REVISION_CONFLICT`, merge still-valid information with the returned current content before submitting again. Session focus is independent; discussion content is shared.

Resume with the same source and stable session identity. A different chat can also locate the task and tree explicitly. A non-null child `next_offset` indicates another page is available.

Discussion records follow the current task's authorization. Code implementation, architectural-intent changes, deployment, and external actions follow their respective task authorizations.
