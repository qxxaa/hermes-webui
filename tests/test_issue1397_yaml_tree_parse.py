"""Tests for issue #1397 — YAML/JSON code blocks show 'parse failed' and
multi-line content renders as a single continuous line in tree view.

Two stacked bugs are fixed:
1. Newlines in data-raw attribute get corrupted by the markdown pipeline
   (replaced by <br>) — fixed by encoding \\n as &#10; in the attribute.
2. js-yaml lazy loading never retries the block — fixed by removing
   data-tree-init and calling _loadJsyamlThen(initTreeViews).
"""
import re

# How many characters of source to inspect when verifying an else-branch.
# The three statements (removeAttribute, _loadJsyamlThen, return) are all
# within the same compact else-block, so 200 chars is a generous upper bound.
_ELSE_BRANCH_WINDOW = 200

# Window used to confirm parseFailed=true is absent from the lazy-load branch.
# The else-block is a few lines; 100 chars easily covers it.
_PARSE_FAILED_CHECK_WINDOW = 100


class TestDataRawNewlineEncoding:
    """Bug 1: \\n in data-raw attribute must be encoded as &#10; so the
    markdown text-processing pipeline (which replaces \\n with <br> for
    non-block-level elements) cannot corrupt the attribute value."""

    def test_newline_encoded_as_numeric_reference(self):
        """data-raw attribute stores newlines as &#10; not as literal \\n."""
        with open("static/ui.js", "r", encoding="utf-8") as f:
            content = f.read()
        # Use a regex so minor whitespace variations in the source don't break
        # the assertion (e.g. spaces around the regex literal or arguments).
        assert re.search(r"replace\s*\(\s*/\\n/g\s*,\s*'&#10;'\s*\)", content), (
            "data-raw attribute must encode \\n as &#10; to protect newlines "
            "from the markdown paragraph-splitter's <br> substitution"
        )

    def test_newline_encoding_applied_before_quote_escaping(self):
        """&#10; replacement must appear before the &quot; replacement in the
        chain, as newlines are encoded first then quotes."""
        with open("static/ui.js", "r", encoding="utf-8") as f:
            content = f.read()
        nl_match = re.search(r"replace\s*\(\s*/\\n/g\s*,\s*'&#10;'\s*\)", content)
        quot_match = re.search(r'replace\s*\(\s*/"/g\s*,\s*\'&quot;\'\s*\)', content)
        assert nl_match, "&#10; encoding not found"
        assert quot_match, "&quot; escaping not found"
        assert nl_match.start() < quot_match.start(), (
            "&#10; encoding should be applied before &quot; escaping"
        )


class TestJsyamlLazyLoadRetry:
    """Bug 2: when jsyaml is not yet loaded, the block must be deferred for
    retry rather than being permanently marked as 'parse failed'."""

    def test_lazy_load_else_branch_calls_load_helper(self):
        """The else-branch must call _loadJsyamlThen(initTreeViews)."""
        with open("static/ui.js", "r", encoding="utf-8") as f:
            content = f.read()
        assert "_loadJsyamlThen(initTreeViews)" in content

    def test_lazy_load_else_branch_removes_init_attr(self):
        """The else-branch must remove data-tree-init so the block can be
        retried after js-yaml loads."""
        with open("static/ui.js", "r", encoding="utf-8") as f:
            content = f.read()
        assert "wrap.removeAttribute('data-tree-init')" in content

    def test_lazy_load_else_branch_returns_early(self):
        """The else-branch must return early so that parse-failed note is not
        appended before jsyaml is available."""
        with open("static/ui.js", "r", encoding="utf-8") as f:
            content = f.read()
        remove_pos = content.find("wrap.removeAttribute('data-tree-init')")
        load_pos = content.find("_loadJsyamlThen(initTreeViews)")
        return_pos = content.find("return;", load_pos)
        assert remove_pos != -1
        assert load_pos != -1
        assert return_pos != -1, "return; not found after _loadJsyamlThen call"
        # All three statements belong to the same compact else-block, so they
        # must all appear within _ELSE_BRANCH_WINDOW characters of each other.
        assert return_pos - remove_pos < _ELSE_BRANCH_WINDOW, (
            f"return; is more than {_ELSE_BRANCH_WINDOW} chars from "
            "removeAttribute — may be in the wrong branch"
        )

    def test_parse_failed_not_set_in_lazy_load_branch(self):
        """parseFailed=true must NOT appear in the lazy-load else-branch."""
        with open("static/ui.js", "r", encoding="utf-8") as f:
            content = f.read()
        remove_pos = content.find("wrap.removeAttribute('data-tree-init')")
        assert remove_pos != -1
        # Inspect only the _PARSE_FAILED_CHECK_WINDOW chars that follow, which
        # covers the entire else-block without pulling in unrelated code.
        branch_snippet = content[remove_pos: remove_pos + _PARSE_FAILED_CHECK_WINDOW]
        assert "parseFailed=true" not in branch_snippet, (
            "parseFailed=true must not be set when deferring to lazy load"
        )
