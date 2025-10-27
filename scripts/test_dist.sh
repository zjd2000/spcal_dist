uv pip install -U dist/spcal-0.0.9-*.whl

uv run python - <<'PY'
import sys, spcal
print("python:", sys.executable)
print("spcal:", spcal.__file__)
PY
