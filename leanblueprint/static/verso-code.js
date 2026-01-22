/**
 * Verso-style interactive code highlighting for leanblueprint
 *
 * Provides:
 * - Tippy.js-based hover tooltips with type signatures
 * - Token binding highlights (highlight all occurrences of a variable)
 * - Tactic state toggles
 * - Error/warning message popups
 *
 * Ported from Verso (https://github.com/leanprover/verso)
 */

window.addEventListener('DOMContentLoaded', () => {
    // Don't show hovers inside of closed tactic states
    function blockedByTactic(elem) {
        let parent = elem.parentNode;
        while (parent && "classList" in parent) {
            if (parent.classList.contains("tactic")) {
                const toggle = parent.querySelector("input.tactic-toggle");
                if (toggle) {
                    return !toggle.checked;
                }
            }
            parent = parent.parentNode;
        }
        return false;
    }

    function blockedByTippy(elem) {
        // Don't show a new hover until the old ones are all closed.
        // Scoped to the nearest "top-level block" to avoid being O(n) in the size of the document.
        var block = elem;
        const topLevel = new Set(["section", "body", "html", "nav", "header", "article", "main"]);
        while (block.parentNode && !topLevel.has(block.parentNode.nodeName.toLowerCase())) {
            block = block.parentNode;
        }
        for (const child of block.querySelectorAll(".token, .has-info")) {
            if (child._tippy && child._tippy.state.isVisible) { return true };
        }
        return false;
    }

    // Token binding highlights - highlight all occurrences of the same variable
    for (const c of document.querySelectorAll(".hl.lean .token")) {
        if (c.dataset.binding != "") {
            c.addEventListener("mouseover", (event) => {
                if (blockedByTactic(c)) { return; }
                const context = c.closest(".hl.lean").dataset.leanContext;
                for (const example of document.querySelectorAll(".hl.lean")) {
                    if (example.dataset.leanContext == context) {
                        for (const tok of example.querySelectorAll(".token")) {
                            if (c.dataset.binding == tok.dataset.binding) {
                                tok.classList.add("binding-hl");
                            }
                        }
                    }
                }
            });
        }
        c.addEventListener("mouseout", (event) => {
            for (const tok of document.querySelectorAll(".hl.lean .token")) {
                tok.classList.remove("binding-hl");
            }
        });
    }

    // Render docstrings with marked.js if available
    if ('undefined' !== typeof marked) {
        for (const d of document.querySelectorAll("code.docstring, pre.docstring")) {
            const str = d.innerText;
            const html = marked.parse(str);
            const rendered = document.createElement("div");
            rendered.classList.add("docstring");
            rendered.innerHTML = html;
            d.parentNode.replaceChild(rendered, d);
        }
    }

    // Initialize Tippy.js hovers
    // leanblueprint embeds hover data in data-lean-hovers attribute on each .lean-code block
    // Build a map from code block to its hover data
    const codeBlockHoverData = new Map();

    document.querySelectorAll('.lean-code[data-lean-hovers]').forEach(codeBlock => {
        try {
            const hoverData = JSON.parse(codeBlock.dataset.leanHovers);
            codeBlockHoverData.set(codeBlock, hoverData);
        } catch (e) {
            console.warn('Failed to parse hover data for code block:', e);
        }
    });

    // Helper to find hover data for an element
    function getHoverDataForElement(element) {
        const codeBlock = element.closest('.lean-code[data-lean-hovers]');
        if (!codeBlock) return null;
        return codeBlockHoverData.get(codeBlock) || null;
    }

    function hideParentTooltips(element) {
        let parent = element.parentElement;
        while (parent) {
            const tippyInstance = parent._tippy;
            if (tippyInstance) {
                tippyInstance.hide();
            }
            parent = parent.parentElement;
        }
    }

    const defaultTippyProps = {
        maxWidth: "none",
        appendTo: () => document.body,
        interactive: true,
        delay: [100, null],
        followCursor: 'initial',
        onShow(inst) {
            const hasVersoHover = inst.reference.dataset.versoHover !== undefined;
            const hasHoverInfo = inst.reference.querySelector(".hover-info");

            // Allow if there's hover data
            if (hasVersoHover || hasHoverInfo) {
                return; // undefined = allow
            }

            // Block if no hover data
            return false;
        },
        content(tgt) {
            const content = document.createElement("span");
            if (tgt.classList.contains('tactic')) {
                const state = tgt.querySelector(".tactic-state").cloneNode(true);
                state.style.display = "block";
                content.appendChild(state);
                content.style.display = "block";
                content.className = "hl lean popup";
            } else {
                content.className = "hl lean";
                content.style.display = "block";
                content.style.maxHeight = "300px";
                content.style.overflowY = "auto";
                content.style.overflowX = "hidden";
                const hoverId = tgt.dataset.versoHover;
                const hoverInfo = tgt.querySelector(".hover-info");
                if (hoverId) {
                    // Get hover data from the code block's embedded data
                    const hoverData = getHoverDataForElement(tgt);
                    const data = hoverData ? hoverData[hoverId] : null;
                    if (data) {
                        const info = document.createElement("span");
                        info.className = "hover-info";
                        info.style.display = "block";
                        info.innerHTML = data;
                        content.appendChild(info);
                        // Render docstrings if marked.js is available
                        if ('undefined' !== typeof marked) {
                            for (const d of content.querySelectorAll("code.docstring, pre.docstring")) {
                                const str = d.innerText;
                                const html = marked.parse(str);
                                const rendered = document.createElement("div");
                                rendered.classList.add("docstring");
                                rendered.innerHTML = html;
                                d.parentNode.replaceChild(rendered, d);
                            }
                        }
                    }
                } else if (hoverInfo) {
                    // The inline info, still used for compiler messages
                    content.appendChild(hoverInfo.cloneNode(true));
                }
                const extraLinks = tgt.parentElement ? tgt.parentElement.dataset['versoLinks'] : null;
                if (extraLinks) {
                    try {
                        const extras = JSON.parse(extraLinks);
                        const links = document.createElement('ul');
                        links.className = 'extra-doc-links';
                        extras.forEach((l) => {
                            const li = document.createElement('li');
                            li.innerHTML = "<a href=\"" + l['href'] + "\" title=\"" + l.long + "\">" + l.short + "</a>";
                            links.appendChild(li);
                        });
                        content.appendChild(links);
                    } catch (error) {
                        console.error(error);
                    }
                }
            }
            return content;
        }
    };

    // Apply Tippy themes to different token types
    document.querySelectorAll('.hl.lean .const.token, .hl.lean .keyword.token, .hl.lean .literal.token, .hl.lean .option.token, .hl.lean .var.token, .hl.lean .typed.token, .hl.lean .level-var, .hl.lean .level-const, .hl.lean .level-op, .hl.lean .sort').forEach(element => {
        element.setAttribute('data-tippy-theme', 'lean');
    });
    document.querySelectorAll('.hl.lean .has-info.warning').forEach(element => {
        element.setAttribute('data-tippy-theme', 'warning message');
    });
    document.querySelectorAll('.hl.lean .has-info.information').forEach(element => {
        element.setAttribute('data-tippy-theme', 'info message');
    });
    document.querySelectorAll('.hl.lean .has-info.error').forEach(element => {
        element.setAttribute('data-tippy-theme', 'error message');
    });
    document.querySelectorAll('.hl.lean .tactic').forEach(element => {
        element.setAttribute('data-tippy-theme', 'tactic');
    });

    // Initialize Tippy on all hoverable elements
    if (typeof tippy !== 'undefined') {
        const selector = '.hl.lean .const.token, .hl.lean .keyword.token, .hl.lean .literal.token, .hl.lean .option.token, .hl.lean .var.token, .hl.lean .typed.token, .hl.lean .has-info, .hl.lean .tactic, .hl.lean .level-var, .hl.lean .level-const, .hl.lean .level-op, .hl.lean .sort';
        tippy(selector, defaultTippyProps);
    }
});

// Sync Lean proof body visibility with LaTeX proof toggle
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.sbs-container').forEach(function(container) {
        var expandIcon = container.querySelector('.expand-proof');
        var leanProofBody = container.querySelector('.lean-proof-body');

        if (!expandIcon || !leanProofBody) return;

        // Watch for plastex.js changing the expand icon text
        var observer = new MutationObserver(function() {
            var isExpanded = expandIcon.textContent.trim() === '\u25BC';
            leanProofBody.style.display = isExpanded ? 'inline' : 'none';
        });

        observer.observe(expandIcon, { childList: true, characterData: true, subtree: true });
    });
});
