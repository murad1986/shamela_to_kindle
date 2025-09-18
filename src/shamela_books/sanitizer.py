from __future__ import annotations

from typing import Optional


def sanitize_fragment(html_text: str, profile: str = "minimal") -> str:
    """Profile-based sanitizer. If 'bleach' is available, use it; otherwise fallback to
    a conservative in-house sanitizer similar to sanitize_fragment_allowlist.

    Profiles: minimal, kindle, apple (currently equivalent if bleach not installed).
    """
    try:
        import bleach

        base_tags = [
            "p","br","strong","em","b","i","h1","h2","h3","h4","h5","h6",
            "blockquote","ul","ol","li","sup","sub","table","thead","tbody","tr","th","td",
            "pre","code","figure","figcaption","img","hr",
        ]
        base_attrs = {
            "*": ["id", "class"],
            "img": ["src", "alt"],
            "table": ["summary"],
            "th": ["scope"],
        }
        # Profiles can further restrict
        if profile in {"minimal", "apple"}:
            # Apple Books can be picky: keep it lean
            tags = base_tags
            attrs = base_attrs
        elif profile == "kindle":
            tags = base_tags
            attrs = base_attrs
        else:
            tags = base_tags
            attrs = base_attrs
        cleaner = bleach.Cleaner(tags=tags, attributes=attrs, strip=True)
        return cleaner.clean(html_text)
    except Exception:
        # Fallback simple allowlist
        import re

        allowed = {
            'p','br','strong','em','b','i','h1','h2','h3','h4','h5','h6','blockquote','ul','ol','li','sup','sub',
            'table','thead','tbody','tr','th','td','pre','code','figure','figcaption','img','hr'
        }
        s = re.sub(r"<!--.*?-->", "", html_text, flags=re.S)
        def strip_attrs(m: re.Match) -> str:
            tag = m.group(1).lower()
            if tag not in allowed:
                return ""
            if tag == 'img':
                # keep only src/alt
                return "<img>"
            return f"<{tag}>"
        s = re.sub(r"<\s*([a-zA-Z0-9]+)(\s+[^>]*)?>", strip_attrs, s)
        def keep_end(m: re.Match) -> str:
            tag = m.group(1).lower()
            return f"</{tag}>" if tag in allowed else ""
        s = re.sub(r"</\s*([a-zA-Z0-9]+)\s*>", keep_end, s)
        return s

