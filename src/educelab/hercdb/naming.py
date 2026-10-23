"""What an artifact is, worked out from its names (#23).

The graph only knows PHerc, Cornice and Pezzo, and every object is filed under
a PHerc slot, so a tavoletta arrives as ``("tavoletta", "Cass. 38 (A)", None)``
and a tray of scorze as ``("90", "Scorze da 90 a 223", None)``. These functions
read the three display names the way the catalogue spreadsheet does and give
the object's **kind**, its unwrapping **method**, and a readable **label**.

Nothing here is stored and no display name is changed: display names are the
join key between the source sheets and the graph (see CLAUDE.md). The rules
are ported from the pipeline UI's ``app/services/naming.py`` (``ui-redesign``)
with the kind names of ``docs/papyrus_tray_model.md``; terms are defined in
``docs/glossary.md``. Rules that rest on an unanswered question are tagged
with its id from ``docs/open_questions.md``.
"""
import re

# PHerc nodes that hold drawer material rather than a papyrus. The uuid sheet
# needs a value in its PHerc column, so these stand in. Exact displayNames.
PLACEHOLDERS = ('tavoletta', 'Cassetto', 'frammenti')

PAPYRUS = 'papyrus'
CORNICE = 'cornice'
SCORZA = 'scorza'
PEZZO = 'pezzo'
CASSETTO_PIECE = 'cassetto_piece'
WHOLE_CASSETTO = 'whole_cassetto'
TAVOLETTA = 'tavoletta'
FRAMMENTI = 'frammenti'

OSLOENSE = 'Osloense'
FACKELMANN = 'Fackelmann'

_CASS = re.compile(r"^(?:cass\.|cassetto)\s*(\d+)\s*(.*)$", re.IGNORECASE)
# "pz in Cass. 7": a piece kept in a cassetto, named by where it is.
_PIECE_IN_CASS = re.compile(r"^pz in cass", re.IGNORECASE)
_LETTER = re.compile(r"^\(([A-Z])\)$")
_ROMAN = re.compile(r"^[IVXLC]+$")
# "(Oslo)" is a spelling of "(Osloense)" (Q-04, closed).
_METHOD = re.compile(r"\(?\b(Osloense|Oslo|Fackelmann)\)?\s*$", re.IGNORECASE)


def tidy(value: str | None) -> str | None:
    """A name with the spacing and typos seen live evened out, or None if blank.

    "Cass.106" -> "Cass. 106", "s. n." -> "s.n.", "10 Osloense)" ->
    "10 (Osloense)", and a lone "." (one cornice is named that) -> None.
    """
    if value is None:
        return None
    value = re.sub(r"\b([Cc])ass\.\s*(\d)", r"\1ass. \2", str(value).strip())
    value = value.replace("s. n.", "s.n.")
    value = re.sub(r"(\d) \(?(Osloense|Fackelmann)\)?$", r"\1 (\2)", value)
    return None if value in ("", ".") else value


def is_papyrus(pherc: str | None) -> bool:
    """Whether a PHerc slot names a papyrus, rather than a placeholder for
    drawer material ("tavoletta", "Cassetto") or loose material ("frammenti",
    "folded sheet").

    A lowercase name is loose material unless it names a cassetto piece
    ("cass.75 s. n. B"). Assumption Q-19: that includes "folded sheet",
    "frammento di papiro ercolanese" and "s.n. frammenti 1-2".
    """
    pherc = tidy(pherc)
    if not pherc or pherc in PLACEHOLDERS:
        return False
    return not pherc[0].islower() or bool(_CASS.match(pherc))


def object_kind(pherc: str | None, cornice: str | None = None, pezzo: str | None = None) -> str | None:
    """The kind of the object these names locate (see the module constants).

    With only ``pherc``, the PHerc node itself: ``papyrus``, or None for a
    placeholder or loose material, which is not an object of its own.
    """
    has_cornice, has_pezzo = cornice is not None, pezzo is not None
    pherc, cornice, pezzo = tidy(pherc), tidy(cornice), tidy(pezzo)
    if not pherc:
        return None
    if has_pezzo:
        return PEZZO
    if not has_cornice:
        return PAPYRUS if is_papyrus(pherc) else None
    if not cornice:
        return CORNICE  # one cornice is named "."
    # Assumption Q-09: every tray under the "Cassetto" placeholder is a whole
    # cassetto (Cass. 51, 52 and 98).
    if pherc == 'Cassetto':
        return WHOLE_CASSETTO
    if pherc == 'tavoletta':
        return TAVOLETTA
    if not is_papyrus(pherc):
        return FRAMMENTI
    if _CASS.match(cornice) or _PIECE_IN_CASS.match(cornice):
        return CASSETTO_PIECE
    if cornice.lower().startswith('scorz'):
        return SCORZA
    return CORNICE


def method(cornice: str | None) -> str | None:
    """The unwrapping method named in a cornice ("1 (Osloense)"), or None."""
    found = _METHOD.search(tidy(cornice) or '')
    if not found:
        return None
    return FACKELMANN if found[1].lower() == 'fackelmann' else OSLOENSE


def label_parts(pherc: str | None, cornice: str | None = None, pezzo: str | None = None) -> list[str]:
    """The object's readable name as a lineage, outermost first:
    ["PHerc. 90", "Scorze da 90 a 223"], ["Tavoletta A", "Cassetto 38"].
    Empty when there is nothing to go on."""
    pherc, cornice, pezzo = tidy(pherc), tidy(cornice), tidy(pezzo)
    if not pherc:
        return []
    drawer = _CASS.match(cornice or '')
    parts = _drawer_object(pherc, drawer) if drawer else None
    if parts is None:
        parts = [_papyrus_name(pherc)]
        if cornice:
            parts.append(_container(cornice))
    if pezzo:
        parts.append(f"Pezzo {pezzo}")
    return parts


def label(pherc: str | None, cornice: str | None = None, pezzo: str | None = None) -> str | None:
    """``label_parts`` joined: "PHerc. 90, Scorze da 90 a 223"."""
    return ", ".join(label_parts(pherc, cornice, pezzo)) or None


def describe(pherc: str | None, cornice: str | None = None, pezzo: str | None = None) -> dict:
    """``{kind, method, label, label_parts}`` for one object, the fields the
    REST artifact views add to each node."""
    parts = label_parts(pherc, cornice, pezzo)
    return {
        'kind': object_kind(pherc, cornice, pezzo),
        'method': method(cornice),
        'label': ", ".join(parts) or None,
        'label_parts': parts,
    }


def describe_tray(artifacts: list[dict]) -> dict:
    """``{kind, method, label, papyri}`` for a tray, from the artifacts its
    EduceLabID is assigned to (dicts with ``pherc``/``cornice``/``pezzo``).

    Kind and method are its most specific object's: a cornice-level object over
    a pezzo on it (``02160e53``), any object over the bare papyrus (as 72,
    1362 and 1363 were before #40). ``papyri`` are the papyrus names on the
    tray in natural order. With one papyrus or none, the label is that
    object's; with several it is the tray's own name and the papyri,
    "Cornice 1 (Osloense): PHerc. 216, 219, 225".
    """
    described = [(a, describe(a['pherc'], a['cornice'], a['pezzo'])) for a in artifacts]
    if not described:
        return {'kind': None, 'method': None, 'label': None, 'papyri': []}
    rank = {PAPYRUS: 2, PEZZO: 1}
    artifact, tray = min(described, key=lambda d: rank.get(d[1]['kind'], 0))
    papyri = sorted({a['pherc'] for a, _ in described if is_papyrus(a['pherc'])}, key=_natural_key)
    label_ = tray['label']
    if len(papyri) > 1:
        # Numbered papyri share one "PHerc." prefix; others keep their own names.
        names = [_papyrus_name(tidy(p)) for p in papyri]
        numbered = [n.removeprefix("PHerc. ") for n in names if n.startswith("PHerc. ")]
        names = (["PHerc. " + ", ".join(numbered)] if numbered else []) + \
                [n for n in names if not n.startswith("PHerc. ")]
        own = ', '.join(tray['label_parts'][1:])
        label_ = f"{own}: {', '.join(names)}" if own else ', '.join(names)
    return {'kind': tray['kind'], 'method': tray['method'], 'label': label_, 'papyri': papyri}


def _natural_key(text: str) -> list[tuple]:
    """Sort key under which "216" < "1081" (as ``db.connection._natural_key``)."""
    return [(1, int(c), "") if c.isdigit() else (0, 0, c.lower())
            for c in re.split(r"(\d+)", text) if c]


def _drawer_object(pherc: str, drawer: re.Match) -> list[str] | None:
    """The lineage of a drawer object that isn't part of a papyrus, or None for
    a papyrus's own piece kept in a drawer (named the ordinary way)."""
    number, rest = drawer.groups()
    where = f"Cassetto {number}"
    if pherc == 'Cassetto':
        # Assumption Q-10: a whole cassetto is labelled by itself, "Cassetto 51 (A)".
        return [f"{where} {rest}".strip()]
    if pherc == 'tavoletta':
        letter = _LETTER.match(rest)
        if letter:
            return [f"Tavoletta {letter[1]}", where]
        return ["Tavoletta", f"{where} {rest}".strip()]
    if _CASS.match(pherc):
        # An unnumbered piece named after its drawer ("Cassetto 78 s.n. C");
        # the cornice slot only repeats the drawer.
        return [_papyrus_name(pherc)]
    if not pherc[0].isdigit() and not pherc.startswith("PHerc"):
        # Loose material: "frammenti", "folded sheet", "s.n. frammenti 1-2".
        name = pherc[0].upper() + pherc[1:] if pherc.split()[0].isalpha() else pherc
        return [name, where]
    return None


def _papyrus_name(pherc: str) -> str:
    drawer = _CASS.match(pherc)
    if drawer:
        return f"Cassetto {drawer[1]} {drawer[2]}".strip()
    if pherc[0].isdigit() and "PHerc" not in pherc:  # not "4 PHerc. s.n."
        return f"PHerc. {pherc}"
    if pherc.startswith("PHerc"):
        return "PHerc. " + pherc.removeprefix("PHerc").lstrip(". ")
    return pherc  # not a PHerc number, e.g. "Joannowsky Papyrus"


def _container(cornice: str) -> str:
    drawer = _CASS.match(cornice)
    if drawer:
        return f"Cassetto {drawer[1]} {drawer[2]}".strip()
    if cornice[0].isdigit() or _ROMAN.match(cornice):
        return f"Cornice {cornice}"
    return cornice  # "Scorze da 400 a 407", "pz in Cass. 7"
