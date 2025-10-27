import os
import sys
import shutil
import subprocess
from pathlib import Path
from contextlib import contextmanager
import argparse

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "src" / "spcal"

# 需要编译的目录白名单（相对 PKG_ROOT）；默认包含包根目录
INCLUDE_DIRS = ["", "utils"]  # 按需再加，如 "experimental"
# 不编译/不打包的目录（相对 PKG_ROOT）
EXCLUDE_DIRS = {"tests", "scripts", "__pycache__", "log", "__pypackages__", "tools", "experimental"}

# 不编译的文件名集合（相对各自目录）
EXCLUDE_FILES = {"__init__.py"}  # __init__.py 保留为源码
# 如有纯脚本/入口不想编译，可在此追加：EXCLUDE_FILES |= {"gen_vcs_sh.py", ...}


HIDE_SOURCES_DURING_BUILD = True

BACKUP_DIR = ROOT / ".build_tmp_hide"


def _norm_rel(rel: Path) -> str:
    # 把 Path('.') 规范化为 ''，并统一为 POSIX 字符串
    s = rel.as_posix()
    return "" if s == "." else s

def should_take(dir_rel: Path, file_name: str) -> bool:
    dir_str = _norm_rel(dir_rel)

    # 目录黑/白名单
    parts = set(dir_str.split("/")) if dir_str else set()
    if any(p in EXCLUDE_DIRS for p in parts if p):  # 忽略空段
        return False
    if dir_str not in INCLUDE_DIRS:
        return False

    # 文件过滤
    if file_name in EXCLUDE_FILES:
        return False
    if not file_name.endswith(".py"):
        return False
    return True

def iter_py_files():
    for inc in INCLUDE_DIRS:
        base = PKG_ROOT / inc if inc else PKG_ROOT
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            rel = p.parent.relative_to(PKG_ROOT)
            if should_take(rel, p.name):
                yield p


def run(cmd):
    print(">>", " ".join(map(str, cmd)))
    subprocess.check_call(cmd)


@contextmanager
def temporarily_hide_sources(paths):
    BACKUP_DIR.mkdir(exist_ok=True)
    moved = []
    try:
        for p in paths:
            if p.exists():
                dst = BACKUP_DIR / p.name
                # 保持目录层级：在备份目录下复刻相对子路径
                rel_parent = p.parent.relative_to(PKG_ROOT)
                dst_dir = BACKUP_DIR / rel_parent
                dst_dir.mkdir(parents=True, exist_ok=True)
                dst = dst_dir / p.name
                # 确保目标目录存在
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dst))
                moved.append((p, dst))
        yield
    finally:
        # 还原源码
        for orig, bak in moved:
            bak.parent.mkdir(parents=True, exist_ok=True)
            orig.parent.mkdir(parents=True, exist_ok=True)
            if bak.exists():
                shutil.move(str(bak), str(orig))
        # 清理空目录
        for root, dirs, files in os.walk(BACKUP_DIR, topdown=False):
            if not dirs and not files:
                try:
                    Path(root).rmdir()
                except OSError:
                    pass
        if BACKUP_DIR.exists():
            try:
                BACKUP_DIR.rmdir()
            except OSError:
                pass


def compile_one(py_path: Path):
    # 以 “模块扩展” 编译；产物放回原目录旁边（让导入路径保持不变）
    out_dir = py_path.parent
    cmd = [
        sys.executable, "-m", "nuitka",
        "--module", str(py_path),
        "--output-dir=" + str(out_dir),
        "--remove-output",
        "--nofollow-imports",     # 只编译这个模块本身；其余内部模块也会各自被编译
        "--lto=yes",
        "--no-progress",
    ]
    if sys.platform == "win32":
        cmd.append("--msvc=latest")
    else:
        # 如未安装 clang，可注释掉此行用默认编译器
        cmd.append("--clang")
    run(cmd)


def strip_posix(so_path: Path):
    if sys.platform == "win32":
        return
    try:
        run(["strip", str(so_path)])
    except Exception:
        pass


def cleanup_generated(root: Path):
    """
    删除 Nuitka 在源码树（PKG_ROOT）里生成的产物：
    - *.pyi  类型提示桩
    - *.so   Linux/macOS 扩展
    - *.pyd  Windows 扩展
    只作用于 PKG_ROOT（src/spcal），不动 dist/ 目录。
    """
    patterns = ["*.pyi", "*.so", "*.pyd"]
    removed = []
    for pat in patterns:
        for f in root.rglob(pat):
            try:
                f.unlink()
                removed.append(f)
            except FileNotFoundError:
                pass
    if removed:
        print("Cleaned generated files:")
        for f in removed:
            print(" -", f.relative_to(ROOT))
    else:
        print("Nothing to clean under", root)

# ====== 替换 main()：加入 CLI 和清理调用 ======
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-only", action="store_true",
                        help="只清理生成的 .pyi/.so/.pyd，不进行编译和打包")
    parser.add_argument("--no-clean", action="store_true",
                        help="打包后不清理生成的 .pyi/.so/.pyd")
    args = parser.parse_args()

    if args.clean_only:
        cleanup_generated(PKG_ROOT)
        return

    targets = list(iter_py_files())
    if not targets:
        print("No Python files matched. Check INCLUDE_DIRS/EXCLUDE settings.")
        return

    print(f"Found {len(targets)} files to compile.")
    for t in targets:
        compile_one(t)

    # strip 符号表（Linux/macOS）
    for so in PKG_ROOT.rglob("*.so"):
        strip_posix(so)

    if HIDE_SOURCES_DURING_BUILD:
        with temporarily_hide_sources(targets):
            run(["uv", "build", "--wheel"])
    else:
        run(["uv", "build", "--wheel"])

    print("\n✔ Wheel ready under dist/")

    if not args.no_clean:
        cleanup_generated(PKG_ROOT)

if __name__ == "__main__":
    main()
