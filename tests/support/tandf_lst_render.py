"""Shared test support; contains no collected tests."""

from __future__ import annotations
import re
from tests.golden_criteria import golden_criteria_asset


DOI = "10.1080/17538947.2022.2137254"

URL = f"https://www.tandfonline.com/doi/full/{DOI}"


def source_html():
    return golden_criteria_asset(DOI, "original.html").read_text(encoding="utf-8")


FORMULA_PARTS = {
    1: [
        r"Rg",
        r"S_{0}",
        r"\sum\limits_{t}",
        r"M(\alpha_{t})",
        r"\cos(\theta_{t})D_{t}",
        r"\Delta t",
    ],
    2: [
        r"CRg",
        r"S_{0}\int\limits_{t_{1}}^{t_{2}}",
        r"G_{Bt} + G_{Dt} + G_{Gt}",
        r"D_{t}",
        "dt",
    ],
    3: [r"NDVI", r"\frac{{Re}f_{5} - {Re}f_{4}}{{Re}f_{5} + {Re}f_{4}}"],
    4: [
        r"Wetness",
        r"0.1115{Re}f_{2} + 0.1973{Re}f_{3} + 0.3283{Re}f_{4} + 0.3407{Re}f_{5} - 0.7117{Re}f_{6} - 0.4559{Re}f_{7}",
    ],
    5: [
        r"Albedo",
        r"0.356{Re}f_{2} + 0.130{Re}f_{3} + 0.373{Re}f_{4} + 0.085{Re}f_{5} + 0.072{Re}f_{6} + 0.072{Re}f_{7} - 0.0018",
    ],
    6: [r"{NLS}T_{GPLS}", r"{LST}", r" - {{LS}T_{modelGPLS}}"],
    7: [
        r"{LS}T_{modelGPLS}",
        r"a_{1}",
        r"1 - {Albedo}",
        r"\times {CRg}",
        r"+ a_{2}",
        r"{DEM}",
        r"+ a_{3}",
        r"{NDVI}",
        r"+ a_{4}",
        r"{Wetness}",
    ],
    8: [r"{NLS}T_{LPLS}", r"{LST}", r" - {{LS}T_{modelLPLS}}"],
    9: [
        r"{LS}T_{modelLPLS}",
        r"a_{1}(i,",
        r"1 - {Albedo}",
        r"\times {CRg}",
        r"+ a_{2}(i,",
        r"{DEM}",
        r"+ a_{3}(i,",
        r"{NDVI}",
        r"+ a_{4}(i,",
        r"{Wetness}",
    ],
    10: [r"{NLS}T_{GRFR}", r"{LST}", r" - {{LS}T_{modelGRFR}}"],
    11: [
        r"{LS}T_{modelGRFR}",
        r"= f(",
        r"1 - {Albedo}",
        r"\times {CRg}",
        r"{DEM}",
        r"{NDVI}",
        r"{Wetness}",
    ],
    12: [r"{NLS}T_{LRFR}", r"{LST}", r" - {{LS}T_{modelLPLS}}"],
    13: [
        r"{LS}T_{modelLRFR}",
        r"= f_{({i,j})}",
        r"1 - {Albedo}",
        r"\times {CRg}",
        r"{DEM}",
        r"{NDVI}",
        r"{Wetness}",
    ],
}


def assert_formulas(markdown):
    blocks = re.findall(r"\*\*Equation (\d+)\.\*\*\s*\n\$\$\n([^\n]+)\n\$\$", markdown)
    assert [int(n) for n, _ in blocks] == list(range(1, 14))
    assert len(re.findall(r"(?m)^\$\$$", markdown)) == 26
    assert "[Formula unavailable]" not in markdown
    for number, formula in blocks:
        for part in FORMULA_PARTS[int(number)]:

            def canonical(value):
                return re.sub(r"\\(?:;|,|limits)|[{}\s\u2061]", "", value).replace(
                    r"\cos", "cos"
                )

            assert canonical(part) in canonical(formula), (number, part, formula)
        assert "=" in formula
        if int(number) >= 6:
            assert "i," in formula and "j" in formula
    solar = re.search(r"\$([^$]+)\$ is the solar radiation constant", markdown)
    alpha = re.search(r"\$([^$]+)\$ is the solar zenith angle", markdown)
    assert solar and solar.group(1).replace("{", "").replace("}", "") == "S_0"
    assert alpha and alpha.group(1).replace("{", "").replace("}", "") == r"\alpha_t"
    assert "are are the corrected" in markdown  # publisher wording, not a typo to fix
