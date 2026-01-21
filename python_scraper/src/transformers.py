import re
from typing import Tuple


def parse_course_name(full_name: str) -> Tuple[str, str]:

    if not full_name:
        return "", ""

    pattern = r"\s+(L(?:M|MCU)?-[0-9]+)$"

    match = re.search(pattern, full_name)

    if match:

        classe = match.group(1)
        nome = full_name[:match.start()].strip()
        return nome, classe

    return full_name.strip(), ""
