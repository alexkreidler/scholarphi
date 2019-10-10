import re

from explanations.instrument_tex import color_equations

COLOR_PATTERN = (
    r"(.*?)"
    + r"\\llap{"
    + r"\\setlength{\\fboxsep}{0pt}"
    + r"\\colorbox\[rgb\]{[0-9.]+, [0-9.]+, [0-9.]+}{"
    + r"\\textcolor\[rgb\]{[0-9.]+, [0-9.]+, [0-9.]+}{"
    + r"\1"
    + r"}}}"
)


def generate_hue_0():
    while True:
        yield 0


simple_hue_generator = generate_hue_0()


def test_color_equations():
    tex = "$eq1$ and $eq2$"
    colorized = color_equations(tex, simple_hue_generator)[1]
    matches = re.findall(COLOR_PATTERN, colorized)
    assert len(matches) == 2
    assert matches[0] == "$eq1$"
    assert matches[1] == "$eq2$"


def test_color_equation_in_argument():
    tex = "\\caption{$eq1$}"
    colorized = color_equations(tex, simple_hue_generator)[1]
    assert colorized.startswith("\\caption")
    matches = re.findall(COLOR_PATTERN, colorized)
    assert len(matches) == 1
    assert matches[0] == "$eq1$"
