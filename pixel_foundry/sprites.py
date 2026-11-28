"""Hand-authored high-density pixel sprites for the Babylon night-market scene."""

TRAVELER_BITMAP_ROWS = (
    "........................................",
    "..................KKKKKK................",
    ".................GGGGGGGKK..............",
    "...............GGKDDDDDDGGKK............",
    "..............GKDDDDDDDDDDGGK...........",
    "..............GKDDDDDDDDDDDDG...........",
    ".............GKDDDDDDDDDDDDDGK..........",
    ".............GKDPPPPPPPPPDDDKG..........",
    "............GKDPPSSSSSSHHPDDDGK.........",
    "..........KKKDDSSFPHHHHSSPDDDKK.........",
    "..........KKHDFFFFPHHHHHHHPDSKK.........",
    "..........KKHDFFKKKHFHKKKHPDSKK.........",
    "..........KKHDFFFHPHFHHHHPPDSKK.........",
    "..........KKHDFFFFFHFHHHHPPDSKK.........",
    "..........KKHDFFFFFPFPPPPPPDSKK.........",
    "...........KHDFFFFFPPHPPPPPDSK..........",
    "...........KKHDFFFKKKKKKPPDSKK..........",
    "............KHDFFSSSSSSSPDKSK...........",
    "............KKHDFSHSHSHSDDSKK...........",
    ".............SKKDFFFFFFFDKKKS...........",
    ".............SSSSSFFFFFFSSSSS...........",
    "............SSHSSSSFFFFSSSSHS...........",
    "......KKKKKKSKSHSSGSFSGSSHHKSS..........",
    ".....KKKKKKKKKKKHHSGSGSHHKKKKSG.........",
    ".....KSSSSSSKSKKKKKKKKKKKKKSHKKG........",
    ".....KSHSSKHSSSSSKKKKKKKKSHHHHKKG.......",
    ".....KSHSKSSHHSSSSSSSSSSSHGGHHHKG.......",
    ".....KSHGKSSSSHHSCCCCCCCSHHHGGHHKG......",
    ".....KSHSGSSSSSSSCHCCCSCSHHHSSSSHG......",
    ".....KSHKSGGSSSSSCHCGCSCSSHHSSSSK.......",
    ".....KGGKHSSGSSSSCHGGGSCSSHHSSHSKK......",
    ".....KSHSHSSGCSSCCGCHCGCCSCCSSHSSK......",
    ".....KSHSHSSSGCSCCHGGGSCCSCCCSHSSK......",
    ".....KSKSHSSCGHSCCHCGCSCCSCCHSSHSKK.....",
    ".....KSKSHSSSCGSCCHCGCSCCSCCHSSHSKK.....",
    ".....KSSSHSSSHGSCCHCGCSCCSSCHSSHSSK.....",
    ".....KSPPPPSSHSSCCHCGCSCCSSCCHPPPPK.....",
    ".....KKPPPPSSHSSCCHCGCSCCSSCCHPPPPK.....",
    "......PHPPPCSHSCCCHCGCSCCCSCCHPPHPP.....",
    "......PPPPPCSHSCCCKKKKKCCCSKKHKKPPP.....",
    "......KPPPPSKHGGGGKHHHKGGGSSGHSKPPKK....",
    "......KKPSSSKGHGGGKHHHKGGSKSSHSKPKKK....",
    ".....KKKSSSSKKHKKKKHHHKKKSKSHHSKSKKK....",
    ".....KKKSSSSCCHSCCKKKKKCCSKSHSSKSKKK....",
    ".....KKKKSSCCCHSHCCCCCCSSSKSHSSKSKKK....",
    "......KKKSSSSCCSSHHSSSSSSSKKKKKKKKKK....",
    ".......KKKGSSSSCSSSHSSSSSCCSSGGKKKK.....",
    "........KKKGHSSSSSSSSSSSSSSHHSKKKK......",
    ".........KKKKHKGGGGGGGGGGHKKKKK.........",
    "...........KKKKDKKKKHKKKKDKKKKKK........",
    ".............KKDDDDKKKDDDDKK............",
    ".............KDDDDDK.KDDDDDK............",
    ".............KKKKKKK.KKKKKKK............",
    "............KKKKKKKK.KKKKKKKK...........",
    "..........KKGGGGGGKK.KKGGGGGGKK.........",
    "...........KKKKKKKKK.KKKKKKKKK..........",
)

_TRAVELER_COLORS = {
    "K": "dark",
    "D": "blue_stone",
    "S": "sand_shadow",
    "C": "sand",
    "H": "sand_light",
    "G": "gold",
    "P": "skin_mid",
    "F": "skin_shadow",
}


def expand_traveler_bitmap(op: dict) -> list[dict]:
    """Expand the authored 40x56 traveler bitmap without upscaling its cells."""
    x, y = int(op.get("x", 0)), int(op.get("y", 0))
    scale = int(op.get("_detail_scale", 1))
    if scale < 1:
        raise ValueError("traveler_bitmap detail scale must be positive")
    if len(TRAVELER_BITMAP_ROWS) != 56 or any(len(row) != 40 for row in TRAVELER_BITMAP_ROWS):
        raise ValueError("traveler_bitmap must remain exactly 40x56 pixels")
    out = []
    for row_index, row in enumerate(TRAVELER_BITMAP_ROWS):
        for column, symbol in enumerate(row):
            if symbol == ".":
                continue
            if symbol not in _TRAVELER_COLORS:
                raise ValueError(f"Unknown traveler bitmap symbol: {symbol!r}")
            px, py = x + column * scale, y + row_index * scale
            if scale == 1:
                out.append({"type": "pixel", "part": f"traveler-bitmap-{symbol}",
                            "x": px, "y": py, "color": _TRAVELER_COLORS[symbol]})
            else:
                out.append({"type": "rect", "part": f"traveler-bitmap-{symbol}",
                            "x": px, "y": py, "w": scale, "h": scale,
                            "color": _TRAVELER_COLORS[symbol]})
    return out
