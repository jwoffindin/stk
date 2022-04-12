import re

def helper(self, name) -> str:
    return re.sub(r'[^a-z0-9]', '', str(name))
