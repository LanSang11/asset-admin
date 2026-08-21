"""提取 .vue 文件 <script setup> 块，逐一做 node --check 语法验证（只读验证管道）。"""
import re
import os
import subprocess
import tempfile

files = [
    r"src\layout\components\header\components\NotificationBell.vue",
    r"src\views\workbench\index.vue",
    r"src\layout\components\sidebar\components\SideLogo.vue",
]
base = r"/path/to/workspace/asset-system\web"
ok = True
for f in files:
    p = os.path.join(base, f)
    with open(p, encoding="utf-8") as fh:
        content = fh.read()
    m = re.search(r"<script setup>(.*?)</script>", content, re.S)
    if not m:
        print(f"NO SCRIPT BLOCK: {f}")
        ok = False
        continue
    tmp = tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8")
    tmp.write(m.group(1))
    tmp.close()
    r = subprocess.run(["node", "--check", tmp.name], capture_output=True, text=True)
    os.unlink(tmp.name)
    if r.returncode == 0:
        print(f"OK: {f}")
    else:
        ok = False
        print(f"FAIL: {f}\n{r.stderr[:500]}")
print("ALL OK" if ok else "HAS FAILURES")
