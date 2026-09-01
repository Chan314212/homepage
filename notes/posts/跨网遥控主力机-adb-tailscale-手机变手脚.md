---
title: AI Agent 调用手机端侧能力：从平板到主力机
date: 2026-08-31
tags: [自动化, ADB, Android, Tailscale, 折腾]
summary: 把原本只能遥控平板的 ADB 方案搬到非 root 的荣耀主力机上：用 Tailscale 跨网连接，实测完成定闹钟、查快递和查电费，也修正了理论篇里关于 Shizuku 的错误判断。
---

之前，NAS 上的 AI 已经能通过 WiFi ADB 遥控一台平板：读屏、点击、查电费都没问题。但平板不是随身设备，很多真正有用的事情还是发生在手机上。

于是我把这条链路搬到了每天带在身上的荣耀主力机。它没有 root，不能照搬平板上的权限玩法，但可以利用 **Tailscale + ADB** 建立一条跨网通道。最终跑通了三个场景：隔空定闹钟、查看淘宝待收货，以及在手机上查电费。

这篇记录的是从“理论上可行”到“真机真的能跑”的过程，也包括一个需要回头修改理论篇的结论。

## 为什么非 root 也够用

日常自动化里，很多事情并不需要 root：启动 App、读取 UI 树、模拟点击、读取电量和前台窗口，ADB 的 shell 权限已经够用。

真正的难点是连接稳定性：

- 无线调试的端口可能是随机的；
- 手机的局域网地址会随 DHCP 变化；
- 国产 ROM 往往要求设备连接 WiFi 才能打开无线调试；
- 手机重启后，临时的 TCP ADB 状态可能消失。

Tailscale 解决的是网络位置问题。手机和 NAS 都加入同一个虚拟网络后，手机会获得固定的 `100.x` 地址，即使手机改用流量，也不必依赖家里的局域网地址。

```text
NAS / Hermes Agent
       │ adb + 自动重连
       │ Tailscale 虚拟网络
       ▼
荣耀主力机（非 root）
       ├─ 系统闹钟
       ├─ 淘宝界面
       └─ 支付宝生活缴费
```

## 连接方案：固定端口优先，随机端口兜底

第一次用 USB 连接手机后，可以让 adbd 暂时监听 5555：

```bash
adb tcpip 5555
adb connect <手机 Tailscale IP>:5555
```

但这里的“固定”只是当前开机周期内有效：

```bash
service.adb.tcp.port
```

不带 `persist` 前缀，手机重启后通常会回到 USB 模式。因此 host 端脚本不能只认 5555，而应当：

1. 先尝试 `Tailscale IP:5555`；
2. 失败后扫描无线调试可能使用的随机端口；
3. 对每个候选端口执行 `adb connect`；
4. 只有返回 `device`，而不是 `offline`，才算连接成功。

伪逻辑如下：

```python
for port in [5555] + candidate_ports:
    if port_open(phone_ip, port):
        if adb_connect(f"{phone_ip}:{port}") == "device":
            return port
raise ConnectionError("phone ADB unavailable")
```

实测连接成功后，可以读到电量、前台窗口并正常执行 UI 操作。这说明链路不是“端口看起来开着”，而是命令确实已经到达手机。

## 场景一：隔空创建一次性闹钟

荣耀时钟的包名不是常见的 `com.android.deskclock`，而是 `com.hihonor.deskclock`。通过标准的 `ACTION_SET_ALARM` 广播可以调用系统设置闹钟：

```bash
adb shell am start -a android.intent.action.SET_ALARM \
  --ei android.intent.extra.alarm.HOUR 20 \
  --ei android.intent.extra.alarm.MINUTES 18 \
  --es android.intent.extra.alarm.MESSAGE "备注" \
  --ez android.intent.extra.alarm.SKIP_UI true
```

荣耀 MagicOS 对 `SKIP_UI=true` 的处理比我预想得更彻底：它直接创建了一次性闹钟，不需要再手动点确认。

这也推翻了理论篇里原先的绝对表述。之前我以为 `ACTION_SET_ALARM` 只能预填时间、等待用户确认；现在看来，**同一个系统契约在不同 ROM 上可能有不同结果**。写 Android 自动化时，标准文档是起点，真机行为才是结论。

## 场景二：查看淘宝待收货

启动淘宝时，我没有猜具体 Activity，而是使用 Launcher 入口：

```bash
adb shell monkey -p com.taobao.taobao \
  -c android.intent.category.LAUNCHER 1
```

进入“我的淘宝”后，再导出 UI 树并读取待收货数量。这里遇到一个小坑：数量显示在 `content-desc`，不在 `text`。解析器如果只看 `text`，会得到一个没有数字的页面。

因此读取 UI 时，至少要同时检查：

- `text`：可见文字；
- `content-desc`：无障碍描述和部分动态数量。

## 场景三：把电费查询搬到主力机

之前平板上的查电费脚本已经能跑，这次只是把设备连接和部分页面特征迁移到手机端：

```bash
python3 query_electricity_phone.py
python3 query_electricity_phone.py --threshold 20
python3 query_electricity_phone.py --out result.json
```

支付宝“生活缴费”页使用懒加载。刚进入页面时，`uiautomator dump` 可能只有标题和图标，“查看电费”“余额”等内容要过几秒才出现。脚本不能只查一次，而要轮询等待：

```python
def goto_life_fee(max_try=8):
    for _ in range(max_try):
        nodes = dump_and_parse()
        if contains_fee_content(nodes):
            return True
        if is_alipay_home(nodes):
            tap_life_fee_entry(nodes)
        sleep(2)
    return False
```

判断“是否在首页”也很重要。不能只看到“生活缴费”四个字就点击，否则进入生活缴费页后，脚本可能把页面标题误认为入口，反复点错位置。

示例输出中的账户信息已脱敏：

```json
{
  "balance": "6.76",
  "account": "****",
  "company": "南京供电公司",
  "debt": "无欠费",
  "ok": true
}
```

## 关于 Shizuku：实测推翻原结论

理论篇曾经写过：非 root 手机可以用 Shizuku 写入 `persist.service.adb.tcp.port`，让 5555 在重启后继续保持。这个判断后来被实机验证推翻：

1. shell 用户写入 `persist.*` 属性会失败；
2. Shizuku 的权限上限仍然是 adb/shell 级，不等于 root；
3. 官方 issue 也说明，Shizuku 本身不能凭空让一个持久 ADB 端口在重启后自动出现。

如果追求开机后自动恢复，可以研究 Automate、Tasker 等手机端自动化工具；但这意味着额外安装和配置。当前我采用更简单的方案：让 NAS 端自动发现端口并重连。它不够优雅，却少了两层依赖。

## 踩坑总表

| 现象 | 原因 | 解法 |
|---|---|---|
| `persist...` 写入失败 | shell 无权修改持久属性 | 不依赖 Shizuku 固定端口，改 host 自动重连 |
| `adb tcpip` 重启失效 | 临时 TCP 状态不会持久保存 | 接受重启后重连或扫描随机端口 |
| 淘宝 `Error type 3` | Activity 路径会变 | 使用 Launcher 入口 |
| 待收货数量读不到 | 数字在 `content-desc` | 同时解析 `text` 和 `content-desc` |
| 生活缴费入口找不到 | 页面懒加载 | 轮询等待，并区分首页与目标页 |

## 这次实践说明了什么

从平板到主力机，真正新增的不是某条神奇命令，而是一条更可靠的连接策略：Tailscale 负责让设备“找得到”，ADB 负责让命令“发得进去”，UI 树负责让脚本“看得懂”。

它仍然不是一个适合所有人的产品化方案。重启、锁屏、网络和 App 改版都可能让自动化失效。但对自己的设备、自己的日常流程来说，先用 ADB 跑通，再把稳定需求抽成正式工具，往往比一开始就设计完整系统更快。

折腾的意义，不是证明理论永远正确，而是愿意在真机面前承认它错了，然后把方案改到真的能用。
