"""
SubVerso Highlighted JSON to HTML Renderer

This module converts SubVerso's Highlighted JSON data structure to syntax-highlighted HTML.
SubVerso (https://github.com/leanprover/subverso) produces a Highlighted type that represents
syntax-highlighted Lean code with semantic information.

The JSON format follows Lean's ToJson serialization for inductive types.
"""
import json
import base64
from html import escape as html_escape
from typing import Any, Optional


def render_highlighted(highlighted_json: str) -> str:
    """
    Convert SubVerso Highlighted JSON string to syntax-highlighted HTML.

    Args:
        highlighted_json: A JSON string representing a SubVerso Highlighted structure.

    Returns:
        HTML string with syntax highlighting via CSS classes.
    """
    data = json.loads(highlighted_json)
    return _render_node(data)


def render_highlighted_base64(encoded: str) -> str:
    """
    Decode base64-encoded Highlighted JSON and render to HTML.

    Args:
        encoded: Base64-encoded JSON string (commonly passed from LaTeX).

    Returns:
        HTML string with syntax highlighting via CSS classes.
    """
    decoded = base64.b64decode(encoded).decode('utf-8')
    return render_highlighted(decoded)


def _render_node(node: Any) -> str:
    """
    Recursively render a Highlighted node to HTML.

    The Highlighted type in Lean is an inductive type with constructors:
    - token: A single token with semantic kind and content
    - text: Plain text (no highlighting)
    - seq: A sequence of Highlighted nodes
    - span: Highlighted content with attached messages (errors/warnings/info)
    - tactics: Tactic block with goal information
    - point: A zero-width annotation point
    - unparsed: Unparsed text (treated as plain text)

    Args:
        node: A deserialized JSON node representing part of the Highlighted structure.

    Returns:
        HTML string for this node.
    """
    if node is None:
        return ""

    # Handle primitive string (plain text)
    if isinstance(node, str):
        return html_escape(node)

    # Handle arrays (sequences)
    if isinstance(node, list):
        return "".join(_render_node(child) for child in node)

    # Handle objects with tagged constructors
    if not isinstance(node, dict):
        return str(node)

    # Lean's ToJson for inductive types uses tagged format
    # The structure varies based on the constructor

    # token: {"token": {"tok": {"kind": {...}, "content": "..."}}} or {"token": {"kind": ..., "content": ...}}
    if "token" in node:
        token_data = node["token"]
        # Handle wrapped format: {"token": {"tok": {...}}}
        if isinstance(token_data, dict) and "tok" in token_data:
            token_data = token_data["tok"]
        return _render_token(token_data)

    # text: {"text": "..."} or {"text": {"str": "..."}}
    if "text" in node:
        text_data = node["text"]
        # Handle wrapped format: {"text": {"str": "..."}}
        if isinstance(text_data, dict) and "str" in text_data:
            text_data = text_data["str"]
        return html_escape(text_data)

    # seq: {"seq": [...]} or {"seq": {"highlights": [...]}}
    if "seq" in node:
        seq_data = node["seq"]
        # Handle wrapped format: {"seq": {"highlights": [...]}}
        if isinstance(seq_data, dict) and "highlights" in seq_data:
            seq_data = seq_data["highlights"]
        return "".join(_render_node(child) for child in seq_data)

    # span: {"span": {"info": [...], "content": {...}}}
    if "span" in node:
        return _render_span(node["span"])

    # tactics: {"tactics": {"info": [...], "startPos": n, "endPos": m, "content": {...}}}
    if "tactics" in node:
        return _render_tactics(node["tactics"])

    # point: {"point": {"kind": "...", "info": {...}}}
    if "point" in node:
        return _render_point(node["point"])

    # unparsed: {"unparsed": "..."}
    if "unparsed" in node:
        return html_escape(node["unparsed"])

    # Fallback: if node has content directly (for some serialization formats)
    if "kind" in node and "content" in node:
        return _render_token(node)

    # Unknown structure - return empty
    return ""


def _render_token(token: dict) -> str:
    """
    Render a Token to HTML.

    A Token has:
    - kind: Token.Kind (the semantic category)
    - content: String (the actual text)

    Args:
        token: Deserialized Token object.

    Returns:
        HTML span with appropriate CSS class.
    """
    kind = token.get("kind", {})
    content = token.get("content", "")

    css_class = _token_class(kind)
    escaped_content = html_escape(content)

    # Check for sorry - special handling
    if content.strip() == "sorry":
        css_class = "lean-sorry"

    # Add data attributes for hover info if available
    attrs = _token_data_attrs(kind)

    if css_class:
        return f'<span class="{css_class}"{attrs}>{escaped_content}</span>'
    return escaped_content


def _token_class(kind: Any) -> str:
    """
    Map SubVerso Token.Kind to CSS class.

    Token.Kind constructors (from Highlighted.lean):
    - keyword: Keywords like 'def', 'theorem', 'where', etc.
    - const: Constants (defined names)
    - anonCtor: Anonymous constructors
    - var: Local variables (bound by forall, lambda, let, etc.)
    - str: String literals
    - option: Lean options
    - docComment: Documentation comments
    - sort: Type/Prop/Sort
    - levelVar: Universe level variables
    - levelOp: Universe level operators (+, max, imax)
    - levelConst: Universe level constants (0, 1, 2, ...)
    - moduleName: Module names in imports
    - withType: Expression with known type
    - unknown: Unknown/unclassified tokens

    Args:
        kind: The Token.Kind object (may be a dict with constructor tag or string).

    Returns:
        CSS class name (without 'lean-' prefix applied yet, that's added in return).
    """
    if kind is None:
        return "lean-text"

    # Handle string format (simple case)
    if isinstance(kind, str):
        return _kind_string_to_class(kind)

    # Handle dict format (tagged constructor)
    if isinstance(kind, dict):
        # Lean's ToJson for inductive uses the constructor name as key
        # e.g., {"keyword": {"name": null, "occurrence": null, "docs": null}}
        #       {"const": {"name": [...], "signature": "...", "docs": null, "isDef": false}}

        if "keyword" in kind:
            return "lean-keyword"

        if "const" in kind:
            const_data = kind["const"]
            # Check if this is a definition site
            if isinstance(const_data, dict) and const_data.get("isDef", False):
                return "lean-const lean-def"
            return "lean-const"

        if "anonCtor" in kind:
            return "lean-const"

        if "var" in kind:
            return "lean-var"

        if "str" in kind:
            return "lean-string"

        if "option" in kind:
            return "lean-option"

        if "docComment" in kind:
            return "lean-docstring"

        if "sort" in kind:
            return "lean-sort"

        if "levelVar" in kind:
            return "lean-level"

        if "levelOp" in kind:
            return "lean-level"

        if "levelConst" in kind:
            return "lean-level"

        if "moduleName" in kind:
            return "lean-module"

        if "withType" in kind:
            return "lean-expr"

        if "unknown" in kind:
            return "lean-text"

        # Check if kind itself is a simple string value stored differently
        for key in kind:
            if kind[key] is None or kind[key] == {}:
                return _kind_string_to_class(key)

    return "lean-text"


def _kind_string_to_class(kind_name: str) -> str:
    """Map a simple kind name string to CSS class."""
    mapping = {
        "keyword": "lean-keyword",
        "const": "lean-const",
        "anonCtor": "lean-const",
        "var": "lean-var",
        "str": "lean-string",
        "option": "lean-option",
        "docComment": "lean-docstring",
        "sort": "lean-sort",
        "levelVar": "lean-level",
        "levelOp": "lean-level",
        "levelConst": "lean-level",
        "moduleName": "lean-module",
        "withType": "lean-expr",
        "unknown": "lean-text",
    }
    return mapping.get(kind_name, "lean-text")


def _token_data_attrs(kind: Any) -> str:
    """
    Extract data attributes for token hover information.

    Args:
        kind: The Token.Kind object.

    Returns:
        HTML attribute string (with leading space if non-empty).
    """
    if not isinstance(kind, dict):
        return ""

    attrs = []

    # Extract signature for constants
    if "const" in kind:
        const_data = kind["const"]
        if isinstance(const_data, dict):
            sig = const_data.get("signature")
            if sig:
                attrs.append(f'data-signature="{html_escape(sig)}"')
            name = const_data.get("name")
            if name:
                name_str = _name_to_string(name)
                if name_str:
                    attrs.append(f'data-name="{html_escape(name_str)}"')

    # Extract type for variables
    if "var" in kind:
        var_data = kind["var"]
        if isinstance(var_data, dict):
            var_type = var_data.get("type")
            if var_type:
                attrs.append(f'data-type="{html_escape(var_type)}"')

    # Extract docs for keywords
    if "keyword" in kind:
        kw_data = kind["keyword"]
        if isinstance(kw_data, dict):
            docs = kw_data.get("docs")
            if docs:
                attrs.append(f'data-docs="{html_escape(docs)}"')

    if attrs:
        return " " + " ".join(attrs)
    return ""


def _name_to_string(name: Any) -> str:
    """
    Convert a Lean Name (serialized as array) to string.

    Lean Names are serialized as arrays of components:
    e.g., ["Nat", "add"] -> "Nat.add"

    Args:
        name: The serialized Name (array of strings/numbers).

    Returns:
        Dot-separated name string.
    """
    if isinstance(name, list):
        return ".".join(str(component) for component in name)
    if isinstance(name, str):
        return name
    return ""


def _render_span(span: dict) -> str:
    """
    Render a Span to HTML.

    A Span wraps highlighted content with attached messages (errors, warnings, info).

    Structure:
    - info: Array of (Span.Kind, MessageContents) tuples
    - content: Highlighted

    Args:
        span: Deserialized Span object.

    Returns:
        HTML span with appropriate message class.
    """
    info = span.get("info", [])
    content = span.get("content", {})

    # Determine the most severe message type for CSS class
    css_class = "lean-span"
    has_error = False
    has_warning = False
    has_info = False

    for item in info:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            kind = item[0]
        elif isinstance(item, dict):
            kind = item.get("kind") or item.get("fst")
        else:
            kind = item

        if kind == "error":
            has_error = True
        elif kind == "warning":
            has_warning = True
        elif kind == "info":
            has_info = True

    if has_error:
        css_class += " lean-error"
    elif has_warning:
        css_class += " lean-warning"
    elif has_info:
        css_class += " lean-info"

    rendered_content = _render_node(content)

    # Optionally include message content as title/tooltip
    messages = _extract_span_messages(info)
    title_attr = ""
    if messages:
        title_attr = f' title="{html_escape(messages)}"'

    return f'<span class="{css_class}"{title_attr}>{rendered_content}</span>'


def _extract_span_messages(info: list) -> str:
    """
    Extract message text from span info for tooltips.

    Args:
        info: List of (kind, MessageContents) pairs.

    Returns:
        Combined message text.
    """
    messages = []
    for item in info:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            msg_content = item[1]
        elif isinstance(item, dict):
            msg_content = item.get("snd") or item.get("message") or item.get("contents")
        else:
            continue

        text = _message_contents_to_string(msg_content)
        if text:
            messages.append(text)

    return "\n".join(messages)


def _message_contents_to_string(msg: Any) -> str:
    """
    Convert MessageContents to plain text.

    MessageContents constructors:
    - text: Plain text
    - goal: A goal display
    - term: A term/expression
    - trace: A trace message with children
    - append: Concatenation of messages

    Args:
        msg: Deserialized MessageContents object.

    Returns:
        Plain text representation.
    """
    if msg is None:
        return ""

    if isinstance(msg, str):
        return msg

    if isinstance(msg, list):
        return "".join(_message_contents_to_string(m) for m in msg)

    if not isinstance(msg, dict):
        return str(msg)

    # text: {"text": "..."}
    if "text" in msg:
        return msg["text"]

    # append: {"append": [...]}
    if "append" in msg:
        return "".join(_message_contents_to_string(m) for m in msg["append"])

    # goal: {"goal": {...}}
    if "goal" in msg:
        return _goal_to_string(msg["goal"])

    # term: {"term": {...}}
    if "term" in msg:
        return _highlighted_to_string(msg["term"])

    # trace: {"trace": {"cls": ..., "msg": ..., "children": [...], "collapsed": bool}}
    if "trace" in msg:
        trace = msg["trace"]
        if isinstance(trace, dict):
            result = _message_contents_to_string(trace.get("msg", ""))
            children = trace.get("children", [])
            if children and not trace.get("collapsed", True):
                for child in children:
                    result += "\n  " + _message_contents_to_string(child)
            return result

    return ""


def _goal_to_string(goal: dict) -> str:
    """
    Convert a Goal to plain text representation.

    Goal structure:
    - name: Optional case name
    - goalPrefix: The turnstile prefix (e.g., "⊢ ")
    - hypotheses: Array of Hypothesis
    - conclusion: The goal type

    Args:
        goal: Deserialized Goal object.

    Returns:
        Plain text goal representation.
    """
    if not isinstance(goal, dict):
        return ""

    parts = []

    # Case name
    name = goal.get("name")
    if name:
        parts.append(f"case {name}")

    # Hypotheses
    hypotheses = goal.get("hypotheses", [])
    for hyp in hypotheses:
        if isinstance(hyp, dict):
            names = hyp.get("names", [])
            type_and_val = hyp.get("typeAndVal", {})
            name_strs = []
            for n in names:
                if isinstance(n, dict):
                    name_strs.append(n.get("content", ""))
                elif isinstance(n, str):
                    name_strs.append(n)
            type_str = _highlighted_to_string(type_and_val)
            if name_strs:
                parts.append(f"{' '.join(name_strs)} : {type_str}")

    # Conclusion
    prefix = goal.get("goalPrefix", "⊢ ")
    conclusion = _highlighted_to_string(goal.get("conclusion", {}))
    parts.append(f"{prefix}{conclusion}")

    return "\n".join(parts)


def _highlighted_to_string(hl: Any) -> str:
    """
    Convert Highlighted to plain text (stripping all formatting).

    Args:
        hl: A Highlighted node.

    Returns:
        Plain text content.
    """
    if hl is None:
        return ""

    if isinstance(hl, str):
        return hl

    if isinstance(hl, list):
        return "".join(_highlighted_to_string(item) for item in hl)

    if not isinstance(hl, dict):
        return ""

    if "token" in hl:
        token = hl["token"]
        return token.get("content", "") if isinstance(token, dict) else ""

    if "text" in hl:
        return hl["text"]

    if "seq" in hl:
        return "".join(_highlighted_to_string(item) for item in hl["seq"])

    if "span" in hl:
        return _highlighted_to_string(hl["span"].get("content", {}))

    if "tactics" in hl:
        return _highlighted_to_string(hl["tactics"].get("content", {}))

    if "point" in hl:
        return ""

    if "unparsed" in hl:
        return hl["unparsed"]

    return ""


def _render_tactics(tactics: dict) -> str:
    """
    Render a tactics block to HTML.

    Tactics blocks contain goal state information and can be expanded
    to show proof state.

    Structure:
    - info: Array of Goal objects
    - startPos: Start position in source
    - endPos: End position in source
    - content: Highlighted content

    Args:
        tactics: Deserialized tactics object.

    Returns:
        HTML with tactic content and expandable goals.
    """
    info = tactics.get("info", [])
    content = tactics.get("content", {})
    start_pos = tactics.get("startPos", 0)
    end_pos = tactics.get("endPos", 0)

    rendered_content = _render_node(content)

    if not info:
        return f'<span class="lean-tactic">{rendered_content}</span>'

    # Render with expandable goal display
    goals_html = _render_goals(info)
    goal_id = f"goal-{start_pos}-{end_pos}"

    return (
        f'<span class="lean-tactic" data-goals="{goal_id}">'
        f'{rendered_content}'
        f'</span>'
        f'<span class="lean-goals" id="{goal_id}" style="display:none;">'
        f'{goals_html}'
        f'</span>'
    )


def _render_goals(goals: list) -> str:
    """
    Render a list of goals to HTML.

    Args:
        goals: List of Goal objects.

    Returns:
        HTML representation of goals.
    """
    if not goals:
        return '<span class="lean-goal-message">Goals accomplished</span>'

    parts = []
    for i, goal in enumerate(goals):
        parts.append(_render_goal(goal, i + 1, len(goals)))

    return "".join(parts)


def _render_goal(goal: dict, index: int, total: int) -> str:
    """
    Render a single goal to HTML.

    Args:
        goal: A Goal object.
        index: 1-based index of this goal.
        total: Total number of goals.

    Returns:
        HTML for this goal.
    """
    if not isinstance(goal, dict):
        return ""

    parts = []

    # Goal header
    name = goal.get("name")
    if total > 1:
        header = f"goal {index}/{total}"
        if name:
            header = f"case {name} ({index}/{total})"
        parts.append(f'<div class="lean-goal-header">{html_escape(header)}</div>')
    elif name:
        parts.append(f'<div class="lean-goal-header">case {html_escape(name)}</div>')

    # Hypotheses
    hypotheses = goal.get("hypotheses", [])
    if hypotheses:
        parts.append('<div class="lean-hypotheses">')
        for hyp in hypotheses:
            parts.append(_render_hypothesis(hyp))
        parts.append('</div>')

    # Conclusion
    prefix = goal.get("goalPrefix", "⊢ ")
    conclusion = goal.get("conclusion", {})
    parts.append(
        f'<div class="lean-conclusion">'
        f'<span class="lean-turnstile">{html_escape(prefix)}</span>'
        f'{_render_node(conclusion)}'
        f'</div>'
    )

    return f'<div class="lean-goal">{"".join(parts)}</div>'


def _render_hypothesis(hyp: dict) -> str:
    """
    Render a hypothesis to HTML.

    Hypothesis structure:
    - names: Array of Token (the hypothesis names)
    - typeAndVal: Highlighted (the type, possibly with value)

    Args:
        hyp: A Hypothesis object.

    Returns:
        HTML for this hypothesis.
    """
    if not isinstance(hyp, dict):
        return ""

    names = hyp.get("names", [])
    type_and_val = hyp.get("typeAndVal", {})

    # Render names
    name_parts = []
    for name_token in names:
        if isinstance(name_token, dict):
            name_parts.append(_render_token(name_token))
        elif isinstance(name_token, str):
            name_parts.append(html_escape(name_token))

    names_html = " ".join(name_parts)
    type_html = _render_node(type_and_val)

    return (
        f'<div class="lean-hypothesis">'
        f'<span class="lean-hyp-names">{names_html}</span>'
        f'<span class="lean-hyp-colon"> : </span>'
        f'<span class="lean-hyp-type">{type_html}</span>'
        f'</div>'
    )


def _render_point(point: dict) -> str:
    """
    Render a point annotation to HTML.

    Points are zero-width annotations that don't render visible content
    but may carry semantic information.

    Structure:
    - kind: Span.Kind (error/warning/info)
    - info: MessageContents

    Args:
        point: A point object.

    Returns:
        HTML span (typically empty or an icon).
    """
    kind = point.get("kind", "info")
    info = point.get("info", {})

    css_class = f"lean-point lean-point-{kind}"
    message = _message_contents_to_string(info)

    if message:
        return f'<span class="{css_class}" title="{html_escape(message)}"></span>'
    return f'<span class="{css_class}"></span>'


# CSS for syntax highlighting - can be customized
LEAN_HIGHLIGHT_CSS = """
/* SubVerso Lean Syntax Highlighting */
.lean-keyword { color: #8959a8; font-weight: bold; }
.lean-const { color: #4271ae; }
.lean-const.lean-def { font-weight: bold; }
.lean-var { color: #c82829; }
.lean-string { color: #718c00; }
.lean-option { color: #eab700; }
.lean-docstring { color: #8e908c; font-style: italic; }
.lean-sort { color: #3e999f; }
.lean-level { color: #f5871f; }
.lean-module { color: #4271ae; }
.lean-expr { color: inherit; }
.lean-text { color: inherit; }
.lean-sorry { color: #c82829; background-color: #ffeaea; font-weight: bold; }

/* Message spans */
.lean-span { }
.lean-error { text-decoration: wavy underline #c82829; }
.lean-warning { text-decoration: wavy underline #eab700; }
.lean-info { text-decoration: underline dotted #4271ae; }

/* Point markers */
.lean-point { display: inline-block; width: 0; height: 0; }
.lean-point-error::before { content: "●"; color: #c82829; font-size: 0.7em; }
.lean-point-warning::before { content: "●"; color: #eab700; font-size: 0.7em; }
.lean-point-info::before { content: "●"; color: #4271ae; font-size: 0.7em; }

/* Goals display */
.lean-tactic { cursor: pointer; }
.lean-goals {
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 8px;
    margin: 4px 0;
    font-family: monospace;
    font-size: 0.9em;
}
.lean-goal {
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid #eee;
}
.lean-goal:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
}
.lean-goal-header {
    color: #666;
    font-style: italic;
    margin-bottom: 4px;
}
.lean-hypotheses {
    margin-left: 8px;
}
.lean-hypothesis {
    margin: 2px 0;
}
.lean-hyp-names { color: #c82829; }
.lean-hyp-colon { color: #666; }
.lean-conclusion {
    margin-top: 4px;
}
.lean-turnstile {
    color: #666;
    margin-right: 4px;
}
.lean-goal-message {
    color: #718c00;
    font-style: italic;
}
"""


def get_css() -> str:
    """
    Get the CSS styles for SubVerso syntax highlighting.

    Returns:
        CSS string that can be included in a style tag or CSS file.
    """
    return LEAN_HIGHLIGHT_CSS
