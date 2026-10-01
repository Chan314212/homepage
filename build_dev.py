#!/usr/bin/env python3
"""个人主页 · 开发相关板块构建脚本
用法: python3 build_dev.py

生成：
  dev/index.html         开发相关入口（工具列表）
  dev/webadb/index.html  网页 ADB 工具（WebUSB 直连手机启动 Shizuku / 黑域）

工具页依赖同目录的 webadb.js，由 tools/webadb（npm + esbuild）打包生成：
  cd tools/webadb && npm install && npm run build
"""
import html
from datetime import datetime
from pathlib import Path

from build_notes import BASE_CSS
from site_meta import head_meta

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "dev"

DEV_DESC = ("陈鸿晖的开发相关：能直接用的在线小工具，以及折腾 Android、Linux、"
            "自托管时攒下的东西。第一个工具是网页版 ADB——不用装驱动，"
            "在浏览器里给手机启动 Shizuku 和黑域。")

ADB_DESC = ("网页 ADB 工具：浏览器通过 WebUSB 直连手机，执行 adb 命令启动 Shizuku "
            "与黑域（Brevent）服务，全程不安装 SDK Platform Tools。"
            "需要桌面版 Chrome / Edge。")

TOOL_CSS = """
.list-title { padding: 40px 0 8px; font-size: clamp(1.8rem, 5vw, 2.4rem); }
.list-sub { color: var(--muted); font-size: .92rem; margin: 10px 0 28px; }
.note-card {
  display: block; text-decoration: none;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 20px 24px; margin-bottom: 16px;
  transition: border-color .2s, transform .2s;
}
.note-card:hover { border-color: var(--accent); transform: translateY(-2px); }
.note-card h3 { color: var(--text); font-size: 1.08rem; }
.note-card .summary { color: var(--muted); font-size: .9rem; margin-top: 8px; }
.note-card .tags { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; }
.tool-card { padding-bottom: 28px; }

/* ---- 工具页 ---- */
.status-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 14px 18px; margin: 18px 0;
}
.dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: var(--muted); flex: 0 0 auto;
}
body[data-state="connected"] .dot { background: var(--accent); box-shadow: 0 0 8px rgba(126,224,163,.8); }
.status-text { font-size: .92rem; }
.btn-row { display: flex; flex-wrap: wrap; gap: 10px; margin: 14px 0; }
.btn {
  font-family: inherit; font-size: .9rem; cursor: pointer;
  background: var(--bg-soft); color: var(--text);
  border: 1px solid var(--border); border-radius: 999px;
  padding: 9px 20px; transition: border-color .2s, transform .2s, background .2s;
}
.btn:hover:not(:disabled) { border-color: var(--accent); transform: translateY(-2px); }
.btn:disabled { opacity: .45; cursor: not-allowed; }
.btn.primary { border-color: var(--accent); color: var(--accent); }
.btn.primary:hover:not(:disabled) { background: rgba(126,224,163,.1); }
.btn.ghost { border-color: var(--border); color: var(--muted); }
.panel {
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 18px; margin: 16px 0;
}
.panel h3 { font-size: .95rem; margin-bottom: 10px; color: var(--text); }
.panel pre {
  margin: 0; white-space: pre-wrap; word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .82rem; color: var(--muted); line-height: 1.7;
}
#logs {
  background: #0b0f14; border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 16px; height: 340px; overflow-y: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .8rem; line-height: 1.65; white-space: pre-wrap; word-break: break-all;
}
#logs .info { color: #9aa4b2; }
#logs .cmd { color: #58a6ff; }
#logs .succ { color: var(--accent); }
#logs .warn { color: #e3b341; }
#logs .error { color: #f8766d; }
.cmd-input {
  display: flex; gap: 10px; margin-top: 12px;
}
.cmd-input input {
  flex: 1; font-family: ui-monospace, Menlo, monospace; font-size: .85rem;
  background: var(--bg-soft); color: var(--text);
  border: 1px solid var(--border); border-radius: 8px; padding: 9px 12px;
}
.cmd-input input:focus { outline: none; border-color: var(--accent-2); }
.hint { color: var(--muted); font-size: .84rem; }
details { margin: 18px 0; }
details summary {
  cursor: pointer; color: var(--accent-2); font-size: .9rem;
  padding: 6px 0; list-style: none;
}
details summary::-webkit-details-marker { display: none; }
details summary::before { content: '▸ '; }
details[open] summary::before { content: '▾ '; }
details ol, details ul { margin: 8px 0 8px 22px; color: var(--muted); font-size: .88rem; }
details li { margin: 6px 0; }
details code { background: var(--bg-soft); border: 1px solid var(--border); padding: 1px 5px; border-radius: 4px; font-size: .85em; }
"""

# ---------- 逻辑与样式共用的页尾 ----------
FOOTER = """<footer>
  <div class="container"><p>© {year} 陈鸿晖 · <a href="/" style="color:var(--accent-2);text-decoration:none;">主页</a></p><p class="filing"><a class="filing-link" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">苏ICP备2026058485号-1</a> · <a class="filing-link" href="https://beian.mps.gov.cn/#/query/webSearch?code=32011402012693" target="_blank" rel="noopener">苏公网安备32011402012693号</a></p></div>
</footer>"""


def build_dev_index() -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>开发相关 · 陈鸿晖</title>
{head_meta("开发相关 · 陈鸿晖", DEV_DESC, "/dev/")}
<style>{BASE_CSS}{TOOL_CSS}</style>
</head>
<body>
<div class="container">
  <div class="topbar"><a href="/">← 返回主页</a></div>
  <h1 class="list-title">开发相关</h1>
  <p class="list-sub">能直接用的在线小工具，以及折腾 Android、Linux、自托管时攒下的东西。<br>
  没有后端，跑在你自己的浏览器里。</p>

  <a class="note-card tool-card" href="/dev/webadb/">
    <h3>🔌 网页 ADB 工具</h3>
    <div class="summary">数据线连上手机，在浏览器里执行 adb 命令，启动 Shizuku 和黑域（Brevent）服务。
    不用装 SDK Platform Tools，不用命令行。</div>
    <div class="tags"><span class="tag">WebUSB</span><span class="tag">Shizuku</span><span class="tag">黑域</span><span class="tag">免 root</span></div>
  </a>

  <p class="hint">这个板块会陆续放更多东西：脚本、小工具、折腾记录里抽出来的可复用部分。</p>
</div>
{FOOTER.format(year=datetime.now().year)}
</body>
</html>"""


def build_webadb_page() -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>网页 ADB 工具 · 启动 Shizuku 与黑域 · 陈鸿晖</title>
{head_meta("网页 ADB 工具 · 启动 Shizuku 与黑域 · 陈鸿晖", ADB_DESC, "/dev/webadb/")}
<style>{BASE_CSS}{TOOL_CSS}</style>
</head>
<body data-state="idle" data-busy="0">
<div class="container">
  <div class="topbar"><a href="/dev/">← 返回开发相关</a> · <a href="/">主页</a></div>
  <h1 class="list-title">网页 ADB 工具</h1>
  <p class="list-sub">浏览器直接走 WebUSB 跟手机说话，执行 adb 命令启动 <strong>Shizuku</strong> 和
  <strong>黑域（Brevent）</strong>。不装 adb，不敲命令行。所有命令都在你的浏览器和手机之间完成，
  这个页面没有后端，也不上传任何数据。</p>

  <div class="status-bar">
    <span class="dot"></span>
    <span class="status-text" id="statusText">未连接</span>
  </div>

  <div class="btn-row">
    <button class="btn primary" id="btnConnect">连接手机</button>
    <button class="btn" id="btnAll">一键启动（Shizuku + 黑域）</button>
    <button class="btn" id="btnShizuku">只启动 Shizuku</button>
    <button class="btn" id="btnBrevent">只启动黑域</button>
    <button class="btn ghost" id="btnDetect">重新检测</button>
    <button class="btn ghost" id="btnDisconnect">断开</button>
  </div>

  <div class="panel">
    <h3>设备信息</h3>
    <pre id="deviceInfo">（未连接）</pre>
  </div>

  <div class="panel">
    <h3>服务状态</h3>
    <pre id="detectInfo">（未检测）</pre>
  </div>

  <div class="panel">
    <h3>运行日志 <span class="hint" style="font-weight:400;float:right;cursor:pointer;" id="btnClear">清空</span></h3>
    <div id="logs"></div>
    <div class="cmd-input">
      <input id="cmdInput" type="text" placeholder="手动执行 adb 命令，例如 ps -A -o NAME | grep shizuku" spellcheck="false">
      <button class="btn" id="btnRun">执行</button>
    </div>
  </div>

  <details>
    <summary>用之前要注意什么</summary>
    <ol>
      <li>浏览器必须是<strong>桌面版 Chrome 或 Edge</strong>（WebUSB 只有 Chromium 系有；Firefox、Safari、手机浏览器都不行）。</li>
      <li>页面必须是 <code>https</code> 打开（本站就是），本地直接双击 HTML 文件不行。</li>
      <li>手机打开「开发者选项 → USB 调试」，插上数据线，手机上弹「允许 USB 调试」时勾上「始终允许」。</li>
      <li>电脑上的 <code>adb server</code> 或 Android Studio 会独占手机，WebUSB 就抢不到了。先执行 <code>adb kill-server</code> 或关掉相关软件。</li>
      <li>Windows 需要把手机的 ADB 接口换成 WinUSB 驱动（用 Zadig），否则浏览器读不到设备；macOS / Linux 免驱动。</li>
      <li>手机上装好 <strong>Shizuku</strong> 和 <strong>黑域</strong>。Shizuku 建议先打开过一次；黑域不用（激活走的是 <code>app_process</code>，不需要它导出任何脚本）。</li>
      <li>两种方式启动的服务都是临时的，<strong>手机重启后要重新启动一次</strong>。</li>
    </ol>
  </details>

  <details>
    <summary>连不上 / 启动失败怎么排查</summary>
    <ul>
      <li><strong>点「连接手机」没弹窗</strong>：检查地址栏右侧是否被浏览器拦了设备权限弹窗，或换个 USB 口、换根线。</li>
      <li><strong>提示设备被占用</strong>：<code>adb kill-server</code>，关掉 Android Studio、投屏、手机助手类软件，再重连。</li>
      <li><strong>Windows 报 transfer error</strong>：用 Zadig 给手机的 ADB 接口装 WinUSB 驱动（装了厂商驱动的电脑常见）。</li>
      <li><strong>Shizuku 没启动</strong>：把 Shizuku 更新到 v13.6 以上，或先在手机上打开 Shizuku 应用再重试。</li>
      <li><strong>黑域没启动</strong>：本工具按黑域官方方式激活（<code>app_process</code> 加载 apk 里的服务类）。如果日志里没有 brevent 进程，常见原因是黑域版本过旧——升到现行 4.x 再试。另一个办法：Shizuku 起来之后，直接在黑域应用内按提示用 Shizuku 启动，不用数据线。</li>
      <li>确认服务是否起来了，手动执行：<code>ps -A -o NAME | grep -E "shizuku|brevent"</code>。</li>
    </ul>
  </details>

  <details>
    <summary>背后的命令（想看原理的点这里）</summary>
    <ul>
      <li>Shizuku（v13.6+）：<code>pm path moe.shizuku.privileged.api</code> 拿到安装目录，执行其中的 <code>libshizuku.so</code>。</li>
      <li>Shizuku（v11.2+ 旧方式）：<code>sh /storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh</code>。</li>
      <li>黑域（官方方式，见 <a href="https://brevent.sh/" target="_blank" rel="noopener">brevent.sh</a>）：把 <code>pm path me.piebridge.brevent</code> 给出的 <code>base.apk</code> 设为 <code>CLASSPATH</code>，执行 <code>app_process /system/bin me.piebridge.brevent.server.BreventServer bootstrap</code>，它生成并执行 <code>/data/local/tmp/brevent.sh</code> 把服务常驻起来。老版本（3.x）才用存储目录里的 <code>brevent.sh</code>，找不到时工具会自动退回那条路。</li>
      <li>底层用的是 <a href="https://github.com/yume-chan/ya-webadb" target="_blank" rel="noopener">Tango ADB（ya-webadb）</a>，纯浏览器实现的 ADB 协议，MIT 协议。</li>
    </ul>
  </details>
</div>
{FOOTER.format(year=datetime.now().year)}
<script type="module" src="webadb.js"></script>
</body>
</html>"""


def main():
    (OUT_DIR / "webadb").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.html").write_text(build_dev_index(), encoding="utf-8")
    print("  ✓ dev/index.html")
    (OUT_DIR / "webadb" / "index.html").write_text(build_webadb_page(), encoding="utf-8")
    print("  ✓ dev/webadb/index.html")
    bundle = OUT_DIR / "webadb" / "webadb.js"
    if not bundle.exists():
        print("  ! 缺少 dev/webadb/webadb.js —— 先跑：cd tools/webadb && npm install && npm run build")


if __name__ == "__main__":
    main()
