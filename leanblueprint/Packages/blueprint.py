"""
Package Lean blueprint

This depends on the depgraph plugin. This plugin has to be installed but then it is
used automatically.

Options:
* project: lean project path

* showmore: enable buttons showing or hiding proofs (this requires the showmore plugin).

You can also add options that will be passed to the dependency graph package.
"""
import string
from pathlib import Path

from jinja2 import Template
from plasTeX import Command
from plasTeX.Logging import getLogger
from plasTeX.PackageResource import PackageCss, PackageJs, PackageTemplateDir
from plastexdepgraph.Packages.depgraph import item_kind
# Note: render_highlighted_base64 removed - Dress artifacts are now required
from leanblueprint.subverso_render import _renumber_brackets_by_depth
import re

log = getLogger()


def clean_lean_source(source: str) -> tuple[str, str | None]:
    """
    Clean Lean source by stripping docstrings and attributes, then split into signature and proof.

    Args:
        source: Raw Lean source code

    Returns:
        (signature, proof_body) tuple where proof_body is None for definitions
    """
    # Strip /-- ... -/ docstrings (can span multiple lines)
    cleaned = re.sub(r'/--.*?-/', '', source, flags=re.DOTALL)

    # Strip @[...] attributes (can span multiple lines with nested brackets)
    # Handle nested brackets by matching balanced brackets
    def strip_attributes(text: str) -> str:
        result = []
        i = 0
        while i < len(text):
            if text[i:i+2] == '@[':
                # Find matching closing bracket for the opening '[' after '@'
                depth = 1  # Start at 1 because we've seen the opening '[' in '@['
                j = i + 2  # Start after '@['
                while j < len(text):
                    if text[j] == '[':
                        depth += 1
                    elif text[j] == ']':
                        depth -= 1
                        if depth == 0:
                            # Found matching bracket, skip past the attribute
                            i = j + 1
                            # Skip any trailing whitespace/newlines
                            while i < len(text) and text[i] in ' \t\n':
                                i += 1
                            break
                    j += 1
                else:
                    # No matching bracket found, keep the character
                    result.append(text[i])
                    i += 1
            else:
                result.append(text[i])
                i += 1
        return ''.join(result)

    cleaned = strip_attributes(cleaned)

    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    # Split signature from proof body by looking for := by pattern
    # The pattern `:= by\n` indicates a tactic proof
    match = re.search(r':=\s*by\s*\n', cleaned)
    if match:
        signature = cleaned[:match.end()].rstrip()
        proof_body = cleaned[match.end():]
        # Strip leading/trailing whitespace from proof body
        proof_body = proof_body.strip() if proof_body.strip() else None
        return (signature, proof_body)

    # For definitions (no := by pattern), return full cleaned source as signature
    return (cleaned, None)

PKG_DIR = Path(__file__).parent
STATIC_DIR = Path(__file__).parent.parent/'static'


class home(Command):
    r"""\home{url}"""
    args = 'url:url'

    def invoke(self, tex):
        Command.invoke(self, tex)
        self.ownerDocument.userdata['project_home'] = self.attributes['url']
        return []


class github(Command):
    r"""\github{url}"""
    args = 'url:url'

    def invoke(self, tex):
        Command.invoke(self, tex)
        self.ownerDocument.userdata['project_github'] = self.attributes['url'].textContent.rstrip(
            '/')
        return []


class dochome(Command):
    r"""\dochome{url}"""
    args = 'url:url'

    def invoke(self, tex):
        Command.invoke(self, tex)
        self.ownerDocument.userdata['project_dochome'] = self.attributes['url'].textContent
        return []


class graphcolor(Command):
    r"""\graphcolor{node_type}{color}{color_descr}"""
    args = 'node_type:str color:str color_descr:str'

    def digest(self, tokens):
        Command.digest(self, tokens)
        attrs = self.attributes
        colors = self.ownerDocument.userdata['dep_graph']['colors']
        node_type = attrs['node_type']
        if node_type not in colors:
            log.warning(f'Unknown node type {node_type}')
        colors[node_type] = (attrs['color'].strip(), attrs['color_descr'].strip())


class leanok(Command):
    r"""\leanok"""

    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.userdata['leanok'] = True


class notready(Command):
    r"""\notready"""

    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.userdata['notready'] = True


class mathlibok(Command):
    r"""\mathlibok"""

    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.userdata['leanok'] = True
        self.parentNode.userdata['mathlibok'] = True


class lean(Command):
    r"""\lean{decl list} """
    args = 'decls:list:nox'

    def digest(self, tokens):
        Command.digest(self, tokens)
        decls = [dec.strip() for dec in self.attributes['decls']]
        self.parentNode.setUserData('leandecls', decls)
        all_decls = self.ownerDocument.userdata.setdefault('lean_decls', [])
        all_decls.extend(decls)


class discussion(Command):
    r"""\discussion{issue_number} """
    args = 'issue:str'

    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.setUserData(
            'issue', self.attributes['issue'].lstrip('#').strip())


class leanposition(Command):
    r"""\leanposition{file|startLine|startCol|endLine|endCol}

    Source position metadata for linking to the Lean source file.
    Format: absolute_path|start_line|start_col|end_line|end_col
    """
    args = 'position:str'

    def digest(self, tokens):
        Command.digest(self, tokens)
        pos_str = self.attributes['position']
        # Parse the pipe-separated position data
        parts = pos_str.split('|')
        if len(parts) == 5:
            self.parentNode.setUserData('lean_position', {
                'file': parts[0],
                'start_line': int(parts[1]),
                'start_col': int(parts[2]),
                'end_line': int(parts[3]),
                'end_col': int(parts[4])
            })


class leansource(Command):
    r"""\leansource{base64_encoded_json}"""
    args = 'source:str'

    def digest(self, tokens):
        Command.digest(self, tokens)
        # Store base64-encoded SubVerso JSON for later rendering
        self.parentNode.setUserData('leansource_base64', self.attributes['source'])


class leansignaturesource(Command):
    r"""\leansignaturesource{base64_encoded_json}"""
    args = 'source:str'

    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.setUserData('leansignature_base64', self.attributes['source'])


class leanproofsource(Command):
    r"""\leanproofsource{base64_encoded_json}"""
    args = 'source:str'

    def digest(self, tokens):
        Command.digest(self, tokens)
        self.parentNode.setUserData('leanproof_base64', self.attributes['source'])


class leansourcehtml(Command):
    r"""\leansourcehtml{base64_encoded_html}

    Pre-rendered HTML for the full Lean source code.
    This skips the SubVerso JSON → HTML rendering step for faster processing.
    """
    args = 'source:str'

    def digest(self, tokens):
        import base64
        Command.digest(self, tokens)
        # Decode base64 HTML directly - no SubVerso rendering needed!
        try:
            html_bytes = base64.b64decode(self.attributes['source'])
            html_str = html_bytes.decode('utf-8')
            # Apply rainbow bracket coloring
            html_str = _renumber_brackets_by_depth(html_str)
            self.parentNode.setUserData('lean_source_html', html_str)
        except Exception as e:
            raise RuntimeError(f'Failed to decode Dress artifact \\leansourcehtml: {e}') from e


class leansignaturesourcehtml(Command):
    r"""\leansignaturesourcehtml{base64_encoded_html}

    Pre-rendered HTML for just the Lean signature (up to and including :=).
    This skips the SubVerso JSON → HTML rendering step for faster processing.
    """
    args = 'source:str'

    def digest(self, tokens):
        import base64
        Command.digest(self, tokens)
        try:
            html_bytes = base64.b64decode(self.attributes['source'])
            html_str = html_bytes.decode('utf-8')
            # Apply rainbow bracket coloring
            html_str = _renumber_brackets_by_depth(html_str)
            self.parentNode.setUserData('lean_signature_html', html_str)
        except Exception as e:
            raise RuntimeError(f'Failed to decode Dress artifact \\leansignaturesourcehtml: {e}') from e


class leanproofsourcehtml(Command):
    r"""\leanproofsourcehtml{base64_encoded_html}

    Pre-rendered HTML for just the Lean proof body (after :=).
    This skips the SubVerso JSON → HTML rendering step for faster processing.
    """
    args = 'source:str'

    def digest(self, tokens):
        import base64
        Command.digest(self, tokens)
        try:
            html_bytes = base64.b64decode(self.attributes['source'])
            html_str = html_bytes.decode('utf-8')
            # Apply rainbow bracket coloring
            html_str = _renumber_brackets_by_depth(html_str)
            self.parentNode.setUserData('lean_proof_html', html_str)
        except Exception as e:
            raise RuntimeError(f'Failed to decode Dress artifact \\leanproofsourcehtml: {e}') from e


class leanhoverdata(Command):
    r"""\leanhoverdata{base64_encoded_json}

    Hover data JSON mapping hover IDs to their HTML content.
    Used by JavaScript to display type info on hover.
    """
    args = 'data:str'

    def digest(self, tokens):
        import base64
        Command.digest(self, tokens)
        try:
            json_bytes = base64.b64decode(self.attributes['data'])
            json_str = json_bytes.decode('utf-8')
            self.parentNode.setUserData('lean_hover_data', json_str)
        except Exception as e:
            raise RuntimeError(f'Failed to decode Dress artifact \\leanhoverdata: {e}') from e


class leanposition(Command):
    r"""\leanposition{file|startLine|startCol|endLine|endCol}"""
    args = 'position:str'

    def digest(self, tokens):
        Command.digest(self, tokens)
        parts = self.attributes['position'].split('|')
        if len(parts) == 5:
            self.parentNode.setUserData('leanposition', {
                'file': parts[0],
                'startLine': int(parts[1]),
                'startCol': int(parts[2]),
                'endLine': int(parts[3]),
                'endCol': int(parts[4])
            })


class leanproofposition(Command):
    r"""\leanproofposition{file|startLine|startCol|endLine|endCol}"""
    args = 'position:str'

    def digest(self, tokens):
        Command.digest(self, tokens)
        parts = self.attributes['position'].split('|')
        if len(parts) == 5:
            self.parentNode.setUserData('leanproofposition', {
                'file': parts[0],
                'startLine': int(parts[1]),
                'startCol': int(parts[2]),
                'endLine': int(parts[3]),
                'endCol': int(parts[4])
            })


CHECKMARK_TPL = Template("""
    {% if obj.userdata.leanok and ('proved_by' not in obj.userdata or obj.userdata.proved_by.userdata.leanok ) %}
    ✓
    {% endif %}
""")

LEAN_DECLS_TPL = Template("""
    {% if obj.userdata.leandecls %}
    <button class="modal lean">L∃∀N</button>
    {% call modal('Lean declarations') %}
        <ul class="uses">
          {% for lean, url in obj.userdata.lean_urls %}
          <li><a href="{{ url }}" class="lean_decl">{{ lean }}</a></li>
          {% endfor %}
        </ul>
    {% endcall %}
    {% endif %}
""")

GITHUB_ISSUE_TPL = Template("""
    {% if obj.userdata.issue %}
    <a class="github_link" href="{{ obj.ownerDocument.userdata.project_github }}/issues/{{ obj.userdata.issue }}">Discussion</a>
    {% endif %}
""")

LEAN_LINKS_TPL = Template("""
  {% if thm.userdata['lean_urls'] -%}
    {%- if thm.userdata['lean_urls']|length > 1 -%}
  <div class="tooltip">
      <span class="lean_link">Lean</span>
      <ul class="tooltip_list">
        {% for name, url in thm.userdata['lean_urls'] %}
           <li><a href="{{ url }}" class="lean_decl">{{ name }}</a></li>
        {% endfor %}
      </ul>
  </div>
    {%- else -%}
    <a class="lean_link lean_decl" href="{{ thm.userdata['lean_urls'][0][1] }}">Lean</a>
    {%- endif -%}
    {%- endif -%}
""")

GITHUB_LINK_TPL = Template("""
  {% if thm.userdata['issue'] -%}
  <a class="issue_link" href="{{ document.userdata['project_github'] }}/issues/{{ thm.userdata['issue'] }}">Discussion</a>
  {%- endif -%}
""")

LEAN_SOURCE_TPL = Template("""
{% if obj.userdata.lean_source_html %}
<div class="lean-source-panel">
    <div class="lean-source-header">
        <span class="lean-source-title">Lean Source</span>
        {% if obj.userdata.lean_github_permalink %}
        <a href="{{ obj.userdata.lean_github_permalink }}" class="lean-github-link" target="_blank" rel="noopener">View on GitHub</a>
        {% endif %}
    </div>
    <pre class="lean-code"><code>{{ obj.userdata.lean_source_html | safe }}</code></pre>
</div>
{% endif %}
""")


def ProcessOptions(options, document):
    """This is called when the package is loaded."""

    # We want to ensure the depgraph and showmore packages are loaded.
    # We first need to make sure the corresponding plugins are used.
    # This is a bit hacky but needed for backward compatibility with
    # project who used the blueprint package before the depgraph one was
    # split.
    plugins = document.config['general'].data['plugins'].value
    if 'plastexdepgraph' not in plugins:
        plugins.append('plastexdepgraph')
    # And now load the package.
    document.context.loadPythonPackage(document, 'depgraph', options)
    if 'showmore' in options:
        if 'plastexshowmore' not in plugins:
            plugins.append('plastexshowmore')
        # And now load the package.
        document.context.loadPythonPackage(document, 'showmore', {})

    templatedir = PackageTemplateDir(path=PKG_DIR/'renderer_templates')
    document.addPackageResource(templatedir)

    jobname = document.userdata['jobname']
    outdir = document.config['files']['directory']
    outdir = string.Template(outdir).substitute({'jobname': jobname})

    def make_lean_data() -> None:
        """
        Build url and formalization status for nodes in the dependency graphs.
        Also create the file lean_decls of all Lean names referred to in the blueprint.
        """

        project_dochome = document.userdata.get('project_dochome',
                                                'https://leanprover-community.github.io/mathlib4_docs')

        for graph in document.userdata['dep_graph']['graphs'].values():
            nodes = graph.nodes
            for node in nodes:
                leandecls = node.userdata.get('leandecls', [])
                lean_urls = []
                for leandecl in leandecls:
                    lean_urls.append(
                        (leandecl,
                         f'{project_dochome}/find/#doc/{leandecl}'))

                node.userdata['lean_urls'] = lean_urls

                # Require Dress artifacts - no fallback rendering
                # If SubVerso JSON is present but pre-rendered HTML is missing, error
                if node.userdata.get('leansource_base64') and not node.userdata.get('lean_source_html'):
                    raise RuntimeError(
                        f"Missing Dress artifacts for {node}: found \\leansource but not \\leansourcehtml. "
                        "Run Dress to generate pre-rendered HTML artifacts."
                    )

                if node.userdata.get('leansignature_base64') and not node.userdata.get('lean_signature_html'):
                    raise RuntimeError(
                        f"Missing Dress artifacts for {node}: found \\leansignaturesource but not \\leansignaturesourcehtml. "
                        "Run Dress to generate pre-rendered HTML artifacts."
                    )

                if node.userdata.get('leanproof_base64') and not node.userdata.get('lean_proof_html'):
                    raise RuntimeError(
                        f"Missing Dress artifacts for {node}: found \\leanproofsource but not \\leanproofsourcehtml. "
                        "Run Dress to generate pre-rendered HTML artifacts."
                    )

                # Process leanposition: build GitHub permalink and fallback source display
                if node.userdata.get('leanposition'):
                    pos = node.userdata['leanposition']
                    project_github = document.userdata.get('project_github')
                    if project_github:
                        # Convert absolute path to relative path for GitHub
                        file_path = pos['file']
                        # Try to make path relative by finding common project patterns
                        # The working directory is typically blueprint/src, so project root is two levels up
                        working_dir = Path(document.userdata.get('working-dir', ''))
                        project_root = working_dir.parent.parent  # Go from blueprint/src to project root
                        try:
                            rel_path = Path(file_path).relative_to(project_root)
                            file_path = str(rel_path)
                        except ValueError:
                            # If path is already relative or doesn't match, use as-is
                            pass
                        # Build permalink with line range
                        # Default to 'main' branch - this could be made configurable
                        branch = 'main'
                        node.userdata['lean_github_permalink'] = (
                            f"{project_github}/blob/{branch}/{file_path}"
                            f"#L{pos['startLine']}-L{pos['endLine']}"
                        )

                    # Require Dress artifacts when position data is present
                    # File reading fallback is no longer supported - use Dress
                    if not node.userdata.get('lean_signature_html'):
                        raise RuntimeError(
                            f"Missing Dress artifacts for {node}: found \\leanposition but not \\leansignaturesourcehtml. "
                            "Run Dress to generate pre-rendered HTML artifacts."
                        )

                # Require Dress artifacts when proof position data is present
                if node.userdata.get('leanproofposition') and not node.userdata.get('lean_proof_html'):
                    raise RuntimeError(
                        f"Missing Dress artifacts for {node}: found \\leanproofposition but not \\leanproofsourcehtml. "
                        "Run Dress to generate pre-rendered HTML artifacts."
                    )

                used = node.userdata.get('uses', [])
                node.userdata['can_state'] = all(thm.userdata.get('leanok')
                                                 for thm in used) and not node.userdata.get('notready', False)
                proof = node.userdata.get('proved_by')
                if proof:
                    used.extend(proof.userdata.get('uses', []))
                    node.userdata['can_prove'] = all(thm.userdata.get('leanok')
                                                     for thm in used)
                    node.userdata['proved'] = proof.userdata.get(
                        'leanok', False)
                else:
                    node.userdata['can_prove'] = False
                    node.userdata['proved'] = False

            # Link proof nodes to parent theorems: pass lean_proof_html to proof nodes
            for node in nodes:
                if node.userdata.get('lean_proof_html'):
                    proof = node.userdata.get('proved_by')
                    if proof:
                        proof.userdata['lean_proof_from_parent'] = node.userdata['lean_proof_html']

            # Mark proofs that have a parent theorem - they'll be rendered inline
            for node in nodes:
                proof = node.userdata.get('proved_by')
                if proof:
                    proof.userdata['rendered_inline'] = True

            for node in nodes:
                node.userdata['fully_proved'] = all(n.userdata.get('proved', False) or item_kind(
                    n) == 'definition' for n in graph.ancestors(node).union({node}))

        lean_decls_path = Path(document.userdata['working-dir']).parent/"lean_decls"
        lean_decls_path.write_text("\n".join(document.userdata.get("lean_decls", [])))

    document.addPostParseCallbacks(150, make_lean_data)

    document.addPackageResource([PackageCss(path=STATIC_DIR/'blueprint.css')])

    # Add Verso-style interactive hover JavaScript
    # Popper.js must be loaded before Tippy.js
    document.addPackageResource([
        PackageJs(path=STATIC_DIR/'vendor'/'popper.min.js'),
        PackageJs(path=STATIC_DIR/'vendor'/'tippy-bundle.umd.min.js'),
        PackageJs(path=STATIC_DIR/'verso-code.js')
    ])

    colors = document.userdata['dep_graph']['colors'] = {
        'mathlib': ('darkgreen', 'Dark green'),
        'stated': ('green', 'Green'),
        'can_state': ('blue', 'Blue'),
        'not_ready': ('#FFAA33', 'Orange'),
        'proved': ('#9CEC8B', 'Green'),
        'can_prove': ('#A3D6FF', 'Blue'),
        'defined': ('#B0ECA3', 'Light green'),
        'fully_proved': ('#1CAC78', 'Dark green')
    }

    def colorizer(node) -> str:
        data = node.userdata

        color = ''
        if data.get('mathlibok'):
            color = colors['mathlib'][0]
        elif data.get('leanok'):
            color = colors['stated'][0]
        elif data.get('can_state'):
            color = colors['can_state'][0]
        elif data.get('notready'):
            color = colors['not_ready'][0]
        return color

    def fillcolorizer(node) -> str:
        data = node.userdata
        stated = data.get('leanok')
        can_state = data.get('can_state')
        can_prove = data.get('can_prove')
        proved = data.get('proved')
        fully_proved = data.get('fully_proved')

        fillcolor = ''
        if proved:
            fillcolor = colors['proved'][0]
        elif can_prove and (can_state or stated):
            fillcolor = colors['can_prove'][0]
        if item_kind(node) == 'definition':
            if stated:
                fillcolor = colors['defined'][0]
            elif can_state:
                fillcolor = colors['can_prove'][0]
        elif fully_proved:
            fillcolor = colors['fully_proved'][0]
        return fillcolor

    document.userdata['dep_graph']['colorizer'] = colorizer
    document.userdata['dep_graph']['fillcolorizer'] = fillcolorizer

    def make_legend() -> None:
        """
        Extend the dependency graph legend defined by the depgraph plugin
        by adding information specific to Lean blueprints. This is registered
        as a post-parse callback to allow users to redefine colors and their 
        descriptions.
        """
        document.userdata['dep_graph']['legend'].extend([
            (f"{document.userdata['dep_graph']['colors']['can_state'][1]} border",
             "the <em>statement</em> of this result is ready to be formalized; all prerequisites are done"),
            (f"{document.userdata['dep_graph']['colors']['not_ready'][1]} border",
                "the <em>statement</em> of this result is not ready to be formalized; the blueprint needs more work"),
            (f"{document.userdata['dep_graph']['colors']['can_state'][1]} background",
                "the <em>proof</em> of this result is ready to be formalized; all prerequisites are done"),
            (f"{document.userdata['dep_graph']['colors']['proved'][1]} border",
                "the <em>statement</em> of this result is formalized"),
            (f"{document.userdata['dep_graph']['colors']['proved'][1]} background",
                "the <em>proof</em> of this result is formalized"),
            (f"{document.userdata['dep_graph']['colors']['fully_proved'][1]} background", 
                "the <em>proof</em> of this result and all its ancestors are formalized"),
            (f"{document.userdata['dep_graph']['colors']['mathlib'][1]} border",
                "this is in Mathlib"),
        ])

    document.addPostParseCallbacks(150, make_legend)

    document.userdata.setdefault(
        'thm_header_extras_tpl', []).extend([CHECKMARK_TPL])
    document.userdata.setdefault('thm_header_hidden_extras_tpl', []).extend([LEAN_DECLS_TPL,
                                                                             GITHUB_ISSUE_TPL])
    document.userdata['dep_graph'].setdefault('extra_modal_links_tpl', []).extend([
        LEAN_LINKS_TPL, GITHUB_LINK_TPL])

    # Note: Lean source panel is now rendered directly in Thms.jinja2s template
    # via sbs-statement-grid, so we no longer register LEAN_SOURCE_TPL here
