# SPDX-License-Identifier: Apache-2.0
"""EXPERIMENTAL impact of a source change on the outputs of a Pine script (isolated study copy).

Static and deliberately narrow: it follows only what the source lets one follow without executing
it — single-line assignments (`x = …`, `x := …`, `var x = …`) and single-line output calls (plot,
plotshape, plotchar, plotarrow, hline, bgcolor, barcolor, fill, alertcondition). For each output of
the new revision it says, with the chain of definitions that justifies it:

- `may-change`      its value depends (through named definitions) on a definition that changed;
- `stays-identical` it depends on nothing that changed (e.g. a constant level 70);
- `uncertain`       the relation cannot be established (a construct not followed: blocks, loops,
                    functions, tuples, imports, multi-line statements; an unknown name; no literal title).

A dependency is a name used in an expression — never a shared series name or a coincidence of
values. `may-change` is not `will change`: an output can depend on a changed definition and stay
identical on the tested bars. Nothing here executes the script.
"""
import re

OUTPUT_FUNCS = {"plot": "values", "plotshape": "signals", "plotchar": "signals", "plotarrow": "signals",
                "hline": "values", "bgcolor": "styles", "barcolor": "styles", "fill": "styles",
                "alertcondition": "signals", "plotcandle": "values", "plotbar": "values"}
DECLARATIONS = ("indicator", "strategy", "library")
BUILTIN_SERIES = {"open", "high", "low", "close", "volume", "hl2", "hlc3", "ohlc4", "hlcc4", "bar_index", "time",
                  "time_close", "last_bar_index", "timenow", "last_bar_time"}
KEYWORDS = {"and", "or", "not", "true", "false", "na", "if", "else", "for", "to", "by", "while", "switch", "in",
            "var", "varip", "const", "simple", "series", "int", "float", "bool", "string", "color"}
NOT_FOLLOWED = re.compile(r"^\s*(if|else|for|while|switch|import|export|method|type|enum)\b|=>")
ASSIGN = re.compile(r"^(?:(var|varip)\s+)?(?:(?:const|simple|series)\s+)?(?:(?:int|float|bool|string|color)\s+)?"
                    r"([A-Za-z_]\w*)\s*(:=|=)(?!=)\s*(.+)$")


def _code(line):
    """The line without its `//` comment (strings kept; `//@` directive lines dropped)."""
    if line.lstrip().startswith("//@"):
        return ""
    out, q, i = [], None, 0
    while i < len(line):
        c = line[i]
        if q:
            out.append(c)
            if c == "\\" and i + 1 < len(line):
                out.append(line[i + 1]); i += 2; continue
            if c == q:
                q = None
        elif c in ("'", '"'):
            q = c; out.append(c)
        elif c == "/" and line[i + 1:i + 2] == "/":
            break
        else:
            out.append(c)
        i += 1
    return "".join(out).rstrip()


def _split_args(s):
    args, depth, q, cur = [], 0, None, []
    for c in s:
        if q:
            cur.append(c)
            if c == q:
                q = None
            continue
        if c in ("'", '"'):
            q = c
        elif c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == "," and depth == 0:
            args.append("".join(cur).strip()); cur = []; continue
        cur.append(c)
    if "".join(cur).strip():
        args.append("".join(cur).strip())
    return args


def _norm(expr):
    return re.sub(r"\s+", "", expr or "")


def names(expr):
    """User-level names an expression uses: identifiers outside strings, minus named-argument labels,
    keywords, built-in series and namespaced functions (ta.rsi, color.red …)."""
    e = re.sub(r"\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'", " ", expr or "")
    e = re.sub(r"\b[A-Za-z_]\w*\s*=(?!=)", " ", e)                     # named arguments
    out = []
    for m in re.finditer(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", e):
        tok = m.group(0)
        if "." in tok or tok in KEYWORDS or tok in BUILTIN_SERIES or re.fullmatch(r"\d\w*", tok):
            continue
        rest = e[m.end():].lstrip()
        if rest.startswith("("):                                        # a function call: user function = not followed
            out.append(("call", tok)); continue
        out.append(("name", tok))
    return out


def parse(text):
    """Definitions, outputs and lines not followed, of one revision."""
    defs, outputs, unfollowed = {}, [], []
    for n, raw in enumerate(text.splitlines(), 1):
        line = _code(raw)
        if not line.strip():
            continue
        if line[:1] in (" ", "\t"):
            unfollowed.append({"line": n, "text": line.strip(), "why": "indented block or continuation"}); continue
        if NOT_FOLLOWED.search(line):
            unfollowed.append({"line": n, "text": line.strip(), "why": "construct not followed"}); continue
        m = re.match(r"^([A-Za-z_]\w*)\s*\((.*)\)\s*$", line.strip())
        if m and m.group(1) in DECLARATIONS:
            defs["<declaration>"] = [{"line": n, "expr": m.group(2), "op": "="}]; continue
        if m and m.group(1) in OUTPUT_FUNCS:
            args = _split_args(m.group(2)); pos = [a for a in args if not re.match(r"^[A-Za-z_]\w*\s*=(?!=)", a)]
            kw = {a.split("=", 1)[0].strip(): a.split("=", 1)[1].strip() for a in args if re.match(r"^[A-Za-z_]\w*\s*=(?!=)", a)}
            func = m.group(1)
            value = pos[0] if pos else kw.get("series", kw.get("price", kw.get("condition", "")))
            if func == "fill":
                value = ",".join(pos[:2])
            title_arg = kw.get("title") or (pos[1] if len(pos) > 1 else None)
            title = title_arg[1:-1] if title_arg and title_arg[:1] in ("'", '"') and title_arg[-1:] == title_arg[:1] else None
            style = {k: v for k, v in kw.items() if k not in ("title", "series", "price", "condition")}
            style.update({"#%d" % i: a for i, a in enumerate(pos[2:], 2)})
            outputs.append({"line": n, "func": func, "facet": OUTPUT_FUNCS[func], "value": value, "title": title,
                            "key": title, "style": style}); continue
        if line.strip().startswith("["):
            unfollowed.append({"line": n, "text": line.strip(), "why": "tuple assignment"}); continue
        a = ASSIGN.match(line.strip())
        if a:
            defs.setdefault(a.group(2), []).append({"line": n, "expr": a.group(4), "op": a.group(3), "state": a.group(1),
                                                    "text": line.strip()}); continue
        unfollowed.append({"line": n, "text": line.strip(), "why": "statement not followed"})
    return {"defs": defs, "outputs": outputs, "unfollowed": unfollowed}


def _assigned_in(lines):
    out = set()
    for u in lines:
        for m in re.finditer(r"([A-Za-z_]\w*)\s*:?=(?!=)", u["text"]):
            out.add(m.group(1))
    return out


def analyse(old_text, new_text):
    """Outputs of the new revision with may-change / stays-identical / uncertain and the reason."""
    old, new = parse(old_text), parse(new_text)
    changed = {}
    for name in set(old["defs"]) | set(new["defs"]):
        a = [(_norm(d["expr"]), d["op"], d.get("state")) for d in old["defs"].get(name, [])]
        b = [(_norm(d["expr"]), d["op"], d.get("state")) for d in new["defs"].get(name, [])]
        if a != b:
            shown = lambda d: d.get("text") or d["expr"]
            changed[name] = {"from": [shown(d) for d in old["defs"].get(name, [])], "to": [shown(d) for d in new["defs"].get(name, [])],
                             "lines": [d["line"] for d in new["defs"].get(name, [])]}
    ou = {o["key"]: o for o in old["outputs"] if o["key"]}
    unf_old = {_norm(u["text"]) for u in old["unfollowed"]}
    changed_unfollowed = [u for u in new["unfollowed"] if _norm(u["text"]) not in unf_old]
    removed_unfollowed = [u for u in old["unfollowed"] if _norm(u["text"]) not in {_norm(x["text"]) for x in new["unfollowed"]}]
    touched = _assigned_in(new["unfollowed"]) | _assigned_in(old["unfollowed"])
    def closure(expr, label):
        reasons, unknown, seen, stack = [], set(), set(), [(expr, [])]
        while stack:
            e, path = stack.pop()
            for kind, nm in names(e):
                if kind == "call":
                    unknown.add("%s() is a user function (not followed)" % nm); continue
                if nm in seen:
                    continue
                seen.add(nm)
                if nm in touched:
                    unknown.add("%s is assigned in a construct not followed" % nm)
                if nm not in new["defs"]:
                    unknown.add("%s is not defined by a followed assignment" % nm); continue
                pth = path + [nm]
                if nm in changed:
                    c = changed[nm]
                    reasons.append("%s <- %s (line %s changed: %s -> %s)" % (
                        label, " <- ".join(pth), ",".join(map(str, c["lines"])) or "?", " | ".join(c["from"]) or "(absent)",
                        " | ".join(c["to"]) or "(removed)"))
                for d in new["defs"][nm]:
                    stack.append((d["expr"], pth))
        return reasons, unknown, seen

    results = []
    for o in new["outputs"]:
        r = {"output": o["key"], "func": o["func"], "facet": o["facet"], "line": o["line"], "expression": o["value"]}
        if not o["key"]:
            r.update(status="uncertain", because="no literal title: the output cannot be matched to a result series")
            results.append(r); continue
        prev = ou.get(o["key"])
        own = []
        if prev is None:
            own.append("new output (absent from the reference revision)")
        elif _norm(prev["value"]) != _norm(o["value"]):
            own.append("its own expression changed: %s -> %s" % (prev["value"], o["value"]))
        chain_reasons, unknown, seen = closure(o["value"], o["key"])
        chain_reasons = own + chain_reasons
        style_changed = prev is not None and prev["style"] != o["style"]
        r["depends_on"] = sorted(seen)
        if chain_reasons:
            r.update(status="may-change", because=chain_reasons)
        elif unknown:
            r.update(status="uncertain", because=sorted(unknown))
        elif changed_unfollowed or removed_unfollowed:
            r.update(status="uncertain", because=["a line not followed changed (line %s)" % ", ".join(
                str(u["line"]) for u in changed_unfollowed or removed_unfollowed)] if seen else None)
            if not seen:                                                 # a constant cannot be reached by any statement
                r.update(status="stays-identical", because="constant %s: depends on no definition" % o["value"])
        else:
            r.update(status="stays-identical", because=("depends on %s, none of which changed" % ", ".join(sorted(seen))
                                                        if seen else "constant %s: depends on no definition" % o["value"]))
        if unknown and r["status"] == "may-change":
            r["also_uncertain"] = sorted(unknown)
        if style_changed:
            r["style_change"] = {k: (prev["style"].get(k), o["style"].get(k)) for k in sorted(set(prev["style"]) | set(o["style"]))
                                 if prev["style"].get(k) != o["style"].get(k)}
        st_reasons, st_unknown = [], set()
        for arg, expr in sorted(o["style"].items()):
            rs, un, _ = closure(expr, "%s.%s" % (o["key"], arg))
            st_reasons += rs; st_unknown |= un
        if style_changed:
            st_reasons = ["%s argument changed: %s -> %s" % (k, a, b) for k, (a, b) in r["style_change"].items()] + st_reasons
        r["style"] = ({"status": "may-change", "because": st_reasons} if st_reasons else
                      {"status": "uncertain", "because": sorted(st_unknown)} if st_unknown else
                      {"status": "stays-identical", "because": "no style argument depends on a changed definition"})
        results.append(r)
    removed = [k for k in ou if k not in {o["key"] for o in new["outputs"]}]
    declaration_changed = "<declaration>" in changed
    return {"outputs": results, "changed_definitions": {k: v for k, v in changed.items() if k != "<declaration>"},
            "declaration_changed": declaration_changed, "removed_outputs": removed,
            "not_followed": new["unfollowed"],
            "limits": "static, single-line statements only; may-change means the value depends on a changed "
                      "definition, not that it will differ on the tested bars"}


def expectation(an):
    """The expectation derived from the analysis, per output, plus the facets that must stay unchanged."""
    outs = {r["output"]: {"status": r["status"], "facet": r["facet"]} for r in an["outputs"] if r["output"]}
    style_changes = (any(r.get("style_change") or (r.get("style") or {}).get("status") in ("may-change", "uncertain")
                         for r in an["outputs"]) or an["declaration_changed"])
    unchanged = [] if style_changes else ["styles"]
    if not any(u["text"].split("(")[0].split(".")[0] in ("line", "label", "box", "table", "polyline", "linefill")
               or re.search(r"\b(line|label|box|table|polyline|linefill)\.new\b", u["text"]) for u in an["not_followed"]):
        unchanged.append("objects")
    return {"outputs": outs, "unchanged": unchanged, "change": [],
            "may_change": sorted({v["facet"] for v in outs.values() if v["status"] == "may-change"})}
