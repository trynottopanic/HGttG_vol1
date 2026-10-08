"""Release labels are presentation; signed sequence numbers order updates.

Keep accepting the bounded historical labels used by installed generations.
New 0.4.2 builds use the owner-selected two-digit revision spelling.
"""
import re

_LABEL=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
_REVISION=r'(?:0[1-9]|[1-9][0-9])'
_CURRENT=re.compile(r'(?:0\.4\.2(?:\.'+_REVISION+r')?|0\.4\.3\.'+_REVISION+r')\Z')

def valid_label(value):
    return isinstance(value,str) and _LABEL.fullmatch(value) is not None

def valid_build_label(value):
    if not valid_label(value):return False
    # Older release histories and existing tools remain readable/buildable.
    return re.match(r'0\.4\.[23](?:[._-]|$)',value) is None or _CURRENT.fullmatch(value) is not None
