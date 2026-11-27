"""Génère app/site_defaults.json à partir des textes d'origine du site vitrine.
Usage : python scripts/gen_site_defaults.py /chemin/vers/le/depot/PSIE"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import site_texts as st  # noqa: E402


def both(T, key, joiner=None):
    out = {}
    for lang in ("fr", "ar"):
        v = T[lang][key]
        out[lang] = "\n".join(v) if isinstance(v, list) else v
    return out


def main(site: str) -> None:
    sys.path.insert(0, site)
    import content  # noqa: E402
    T = content.T
    res = {}
    for key, (_t, _a, fields) in st.BLOCS.items():
        res[key] = {}
        for name, _l, kind, _h in fields:
            v = both(T, name)
            res[key][name] = v["fr"] if kind == "tel" else v
    for key, (_t, _a, tkey, fields, _title) in st.LISTES.items():
        fr, ar = T["fr"][tkey], T["ar"][tkey]
        rows = []
        for i, item in enumerate(fr):
            other = ar[i] if i < len(ar) else item
            row = {}
            for name, _l, _k in fields:
                a, b = item[name], other[name]
                row[name] = {"fr": "\n".join(a) if isinstance(a, list) else a, "ar": "\n".join(b) if isinstance(b, list) else b}
            rows.append(row)
        res[key] = rows
    Path(__file__).resolve().parents[1].joinpath("app", "site_defaults.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
