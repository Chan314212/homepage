/**
 * 网页 ADB 工具 —— 通过 WebUSB 直连手机，在浏览器里执行 adb 命令。
 * 用途：启动 Shizuku（免 root 特权服务）、启动黑域（Brevent）服务端。
 *
 * 依赖 @yume-chan/adb（Tango ADB，MIT）：浏览器内实现 ADB 协议。
 * 打包：npm run build → dev/webadb/webadb.js
 */
import { Adb, AdbDaemonTransport } from "@yume-chan/adb";
import { AdbDaemonWebUsbDeviceManager } from "@yume-chan/adb-daemon-webusb";
import AdbWebCredentialStore from "@yume-chan/adb-credential-web";

const SHIZUKU_PKG = "moe.shizuku.privileged.api";
const BREVENT_PKG = "me.piebridge.brevent";
const SHIZUKU_START_SH = "/storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh";
const BREVENT_DIR = "/storage/emulated/0/Android/data/me.piebridge.brevent";

const el = (id) => document.getElementById(id);
const logs = el("logs");
const statusText = el("statusText");
let adb = null;
let usbDevice = null;
let busy = false;
const credentialStore = new AdbWebCredentialStore("huey-webadb");

/* ------------------------------------------------------------------ 日志 */

function stamp() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function log(msg, cls) {
  if (msg === undefined || msg === null) return;
  const s = String(msg).replace(/\s+$/, "");
  if (!s) return;
  const line = document.createElement("div");
  line.className = cls || "info";
  line.textContent = `[${stamp()}] ${s}`;
  logs.appendChild(line);
  logs.scrollTop = logs.scrollHeight;
}

function clearLogs() {
  logs.textContent = "";
}

function setStatus(text, state) {
  statusText.textContent = text;
  document.body.dataset.state = state || "idle";
}

function setBusy(value) {
  busy = value;
  document.body.dataset.busy = value ? "1" : "0";
  refreshButtons();
}

/** 没连上设备时，把后续按钮置灰，避免空点。 */
function refreshButtons() {
  const usable = !!adb && !busy;
  ["btnAll", "btnShizuku", "btnBrevent", "btnDetect", "btnDisconnect", "btnRun"].forEach((id) => {
    const node = el(id);
    if (node) node.disabled = !usable;
  });
  const connectBtn = el("btnConnect");
  if (connectBtn) connectBtn.disabled = busy;
}

/* -------------------------------------------------------------- 命令执行 */

async function run(command, options) {
  const opts = options || {};
  if (!adb) throw new Error("尚未连接设备");
  if (!opts.silent) log("$ " + command, "cmd");
  let stdout = "";
  let stderr = "";
  try {
    const shell = adb.subprocess.shellProtocol;
    if (shell && shell.isSupported) {
      const r = await shell.spawnWaitText(command);
      stdout = r.stdout || "";
      stderr = r.stderr || "";
    } else {
      const proc = await adb.subprocess.noneProtocol.spawn(command);
      const reader = proc.output.getReader();
      const decoder = new TextDecoder();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        stdout += decoder.decode(value, { stream: true });
      }
    }
  } catch (err) {
    log("执行出错：" + (err && err.message ? err.message : err), "error");
    throw err;
  }
  if (!opts.silent) {
    if (stdout.trim()) log(stdout.trimEnd());
    if (stderr.trim()) log(stderr.trimEnd(), "warn");
  }
  return { stdout, stderr };
}

/* ------------------------------------------------------------------ 连接 */

function friendlyError(err) {
  const msg = (err && err.message) || String(err);
  if (/DeviceBusyError|already in use|in used|Access denied|Unable to claim/i.test(msg)) {
    log("设备被占用：电脑上的 adb server 或 Android Studio 正握着这台手机。", "warn");
    log("解决：在命令行执行 adb kill-server（关掉 Android Studio / 投屏工具），再重新连接。", "warn");
  } else if (/No device selected/i.test(msg)) {
    log("没有选择设备。", "warn");
  } else if (/LIBUSB|transfer error|NetworkError|not found/i.test(msg)) {
    log("USB 通信失败：多半是驱动问题。Windows 上需要用 Zadig 把手机的 ADB 接口换成 WinUSB 驱动。", "warn");
  } else {
    log("连接失败：" + msg, "error");
  }
}

async function connect() {
  const manager = AdbDaemonWebUsbDeviceManager.BROWSER;
  if (!manager || !navigator.usb) {
    log("这个浏览器不支持 WebUSB。请用桌面版 Chrome 或 Edge（Firefox、Safari、手机浏览器都不行）。", "error");
    return;
  }
  if (busy) return;
  setBusy(true);
  clearLogs();
  try {
    log("浏览器会弹出设备选择框，选中你的手机。");
    usbDevice = await manager.requestDevice();
    if (!usbDevice) {
      log("没有选择设备，已取消。", "warn");
      setStatus("未连接");
      return;
    }
    const raw = usbDevice.raw || {};
    const name = [raw.manufacturerName, raw.productName].filter(Boolean).join(" ").trim();
    log("已选中：" + (name || "未知设备"));

    const connection = await usbDevice.connect();
    log("正在认证，请留意手机屏幕上的「允许 USB 调试」弹窗并勾选「始终允许」。");
    const transport = await AdbDaemonTransport.authenticate({
      serial: usbDevice.serial,
      connection,
      credentialStore,
    });
    adb = new Adb(transport);
    const serial = await adb.getProp("ro.serialno");
    if (!serial) throw new Error("认证未通过");
    setStatus("已连接：" + (name || serial), "connected");
    log("认证通过，设备已连接。", "succ");
    refreshButtons();
    try {
      await showDeviceInfo();
      await detect();
    } catch (err) {
      log("设备信息读取失败：" + (err && err.message ? err.message : err), "warn");
    }
  } catch (err) {
    adb = null;
    usbDevice = null;
    setStatus("未连接");
    friendlyError(err);
  } finally {
    setBusy(false);
  }
}

async function disconnect(silent) {
  try {
    if (adb) await adb.close();
  } catch (err) {
    /* 断开时的异常无所谓 */
  }
  adb = null;
  usbDevice = null;
  el("deviceInfo").textContent = "";
  el("detectInfo").textContent = "（未检测）";
  setStatus("未连接");
  refreshButtons();
  if (!silent) log("已断开。", "warn");
}

async function showDeviceInfo() {
  const props = [
    ["ro.product.brand", "品牌"],
    ["ro.product.model", "型号"],
    ["ro.build.version.release", "Android"],
    ["ro.build.version.sdk", "SDK"],
    ["ro.product.cpu.abi", "ABI"],
  ];
  const values = await Promise.all(props.map((p) => adb.getProp(p[0]).catch(() => "")));
  const lines = [];
  values.forEach((v, i) => {
    if (v) lines.push(props[i][1] + "：" + v);
  });
  el("deviceInfo").textContent = lines.join("\n");
  log(lines.join("　·　"));
}

/* ------------------------------------------------------------ 状态检测 */

async function packagePath(pkg) {
  const { stdout } = await run(`pm path ${pkg}`, { silent: true });
  const paths = (stdout || "")
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.startsWith("package:"))
    .map((s) => s.slice("package:".length));
  // 多行（split apk）时优先 base.apk：app_process 要从它里面加载完整的服务类
  return paths.find((p) => /base\.apk$/.test(p)) || paths[0] || "";
}

async function detect() {
  if (!adb) {
    log("先连接设备。", "warn");
    return;
  }
  log("—— 检测中 ——", "cmd");
  const [shizukuPath, breventPath, ps] = await Promise.all([
    packagePath(SHIZUKU_PKG).catch(() => ""),
    packagePath(BREVENT_PKG).catch(() => ""),
    run(`(ps -A -o NAME 2>/dev/null || ps -A) | grep -E "shizuku|brevent"`, { silent: true })
      .then((r) => r.stdout)
      .catch(() => ""),
  ]);

  const running = ps.trim();
  const shizukuRunning = /shizuku/i.test(running);
  const breventRunning = /brevent/i.test(running);

  const state = [
    `Shizuku：${shizukuPath ? "已安装" : "未安装"}${shizukuRunning ? " · 服务运行中" : ""}`,
    `黑域：${breventPath ? "已安装" : "未安装"}${breventRunning ? " · 服务运行中" : ""}`,
  ];
  el("detectInfo").textContent = state.join("\n") + (running ? "\n运行中的进程：\n" + running : "\n运行中的进程：无");
  log(state.join("　|　"), shizukuRunning || breventRunning ? "succ" : "info");
  if (!shizukuPath) log("没检测到 Shizuku。手机装一个：https://shizuku.rikka.app/", "warn");
  if (!breventPath) log("没检测到黑域。装好并打开一次，让它生成启动脚本。", "warn");
}

/* ------------------------------------------------------- 启动 Shizuku */

async function startShizuku() {
  if (!adb) {
    log("先连接设备。", "warn");
    return;
  }
  const apk = await packagePath(SHIZUKU_PKG);
  if (!apk) {
    log("这台设备没装 Shizuku（" + SHIZUKU_PKG + "）。", "error");
    return;
  }
  const dir = apk.replace(/\/base\.apk$/, "");
  log("Shizuku 安装目录：" + dir);

  // 方式一（Shizuku v13.6+）：直接执行 native 可执行文件 libshizuku.so
  const { stdout: found } = await run(
    `find "${dir}" -name libshizuku.so 2>/dev/null`,
    { silent: true }
  );
  const so = (found || "").split("\n").map((s) => s.trim()).filter(Boolean)[0];
  if (so) {
    log("找到启动文件：" + so);
    await run(`ls -l "${so}"`, { silent: true });
    let out = await run(`"${so}"`);
    if (!/shizuku/i.test(out.stdout + out.stderr)) {
      log("直接执行未成功，尝试补上可执行权限后再跑一次。", "warn");
      await run(`chmod 755 "${so}" 2>/dev/null; "${so}"`);
    }
    return finishShizuku();
  }

  // 方式二（Shizuku v11.2+）：执行 App 导出的 start.sh
  const { stdout: exists } = await run(`ls "${SHIZUKU_START_SH}" 2>/dev/null`, { silent: true });
  if (exists.trim()) {
    log("找到启动脚本：" + SHIZUKU_START_SH);
    await run(`sh "${SHIZUKU_START_SH}"`);
    return finishShizuku();
  }

  log("没找到 Shizuku 的启动文件。", "error");
  log("请先在手机上打开 Shizuku 应用（让它导出启动文件），或把 Shizuku 更新到 v13.6 以上再试。", "warn");
}

async function finishShizuku() {
  const { stdout } = await run(`(ps -A -o NAME 2>/dev/null || ps -A) | grep -i shizuku`, { silent: true });
  if (/shizuku/i.test(stdout)) {
    log("Shizuku 启动成功！现在可以拔掉数据线了（重启手机后需要再来一次）。", "succ");
  } else {
    log("命令跑完了，但没看到 shizuku 进程。把上面的输出发给晖总看看。", "error");
  }
}

/* --------------------------------------------------------- 启动黑域 */

async function startBrevent() {
  if (!adb) {
    log("先连接设备。", "warn");
    return;
  }
  const apk = await packagePath(BREVENT_PKG);
  if (!apk) {
    log("这台设备没装黑域（" + BREVENT_PKG + "）。", "error");
    return;
  }
  log("黑域已安装：" + apk);

  // 黑域官方激活方式（brevent.sh 首页给的就是这一条）：
  //   用 app_process 加载 apk 里的服务类，bootstrap 生成 /data/local/tmp/brevent.sh，
  //   再执行那个脚本把服务常驻起来。
  // 别再找「App 导出到存储目录的 brevent.sh」——现行版本不走那条路（老教程的遗留说法）。
  const bootstrap = `app_process /system/bin me.piebridge.brevent.server.BreventServer bootstrap`;
  const session = [
    `export CLASSPATH='${apk}'`,
    `if command -v timeout >/dev/null 2>&1; then timeout 30 ${bootstrap}; else ${bootstrap}; fi`,
    `ls -l /data/local/tmp/brevent.sh 2>/dev/null || echo "没生成 /data/local/tmp/brevent.sh"`,
    `if [ -f /data/local/tmp/brevent.sh ]; then /system/bin/sh /data/local/tmp/brevent.sh; fi`,
  ].join("; ");
  await run(session);

  const { stdout: ps } = await run(
    `(ps -A -o NAME 2>/dev/null || ps -A) | grep -i brevent`,
    { silent: true }
  );
  if (/brevent/i.test(ps)) {
    log("黑域服务已启动。现在可以拔线了（重启手机后要再来一次）。", "succ");
    return;
  }

  // 兜底：3.x 及更早的黑域用的是 App 存储目录里的 brevent.sh
  log("没看到 brevent 进程，退回去试老版本的脚本路径。", "warn");
  const legacy = [
    `${BREVENT_DIR}/brevent.sh`,
    "/sdcard/Android/data/me.piebridge.brevent/brevent.sh",
  ];
  let script = "";
  for (const path of legacy) {
    const { stdout } = await run(`ls "${path}" 2>/dev/null`, { silent: true });
    if (stdout.trim()) {
      script = path;
      break;
    }
  }
  if (!script) {
    log("两条路都没走通。把上面的日志发我，我看着输出接着查。", "error");
    log("常见原因：黑域版本过旧（建议升到现行 4.x）、系统限制了 app_process 加载第三方 apk、或存储权限异常。", "warn");
    return;
  }
  log("找到老版脚本：" + script);
  await run(`CLASSPATH='${apk}' sh "${script}"`);
  const { stdout: ps2 } = await run(
    `(ps -A -o NAME 2>/dev/null || ps -A) | grep -i brevent`,
    { silent: true }
  );
  if (/brevent/i.test(ps2)) log("黑域服务已启动（走的老版路径）。", "succ");
  else log("老版脚本跑完也没有 brevent 进程，把日志发我。", "error");
}

/* ------------------------------------------------------------ 一键启动 */

async function startAll() {
  if (!adb) {
    log("先连接设备。", "warn");
    return;
  }
  log("—— 一键启动：Shizuku + 黑域 ——", "cmd");
  await startShizuku().catch((e) => log("Shizuku 出错：" + (e.message || e), "error"));
  await startBrevent().catch((e) => log("黑域出错：" + (e.message || e), "error"));
  await detect().catch(() => {});
}

/* ------------------------------------------------------------ 手动命令 */

async function runManual() {
  if (!adb) {
    log("先连接设备。", "warn");
    return;
  }
  const input = el("cmdInput");
  const cmd = input.value.trim();
  if (!cmd) return;
  try {
    await run(cmd);
  } catch (err) {
    /* run() 已经打过日志 */
  }
}

/* -------------------------------------------------------------- 事件绑定 */

document.addEventListener("DOMContentLoaded", () => {
  if (!navigator.usb) {
    log("当前浏览器不支持 WebUSB：Firefox / Safari / 手机浏览器都用不了，请换桌面版 Chrome 或 Edge。", "warn");
    log("另外页面必须是 https（本站就是），本地打开的 file:// 页面不行。", "warn");
  } else {
    log("用数据线把手机连上电脑，手机上开启「开发者选项 → USB 调试」，然后点「连接手机」。");
  }

  refreshButtons();
  el("btnConnect").addEventListener("click", connect);
  el("btnDisconnect").addEventListener("click", () => disconnect(false));
  el("btnDetect").addEventListener("click", () => detect());
  el("btnAll").addEventListener("click", startAll);
  el("btnShizuku").addEventListener("click", () => startShizuku());
  el("btnBrevent").addEventListener("click", () => startBrevent());
  el("btnClear").addEventListener("click", clearLogs);
  el("btnRun").addEventListener("click", runManual);
  el("cmdInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") runManual();
  });

  if (navigator.usb) {
    navigator.usb.addEventListener("disconnect", (event) => {
      if (usbDevice && event.device === usbDevice.raw) disconnect(false);
    });
  }
});
