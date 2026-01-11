import sys
import traceback

code = sys.stdin.read()

try:
    exec(code, {"__builtins__": __builtins__}, {})
except Exception:
    traceback.print_exc()
