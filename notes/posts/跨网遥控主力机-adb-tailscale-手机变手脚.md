---
title: AI Agent 调用手机端侧能力的方案探索（实践篇）
date: 2026-08-31
tags: [自动化, ADB, Android, Tailscale, 折腾]
summary: 之前用 WiFi ADB 遥控的是平板，这次把一台非 root 的荣耀主力机也接进来——靠 Tailscale 跨网固定连接，让服务器上的 AI 能隔空定闹钟、查快递、查电费。从理论走到实践，还顺手推翻了理论篇里"Shizuku 让 adb 重启自保持"的说法。
---

家里那台 NAS 上的 AI（我这套数字管家）之前已经能遥控**平板**——WiFi ADB、读屏点击、自动查电费。但平板有个尴尬：它是"副机"，平时不随身带，很多要手机本地干的事它顶不上。

最近我把它升级了：**让 AI 直接遥控我天天揣兜里的主力机**。这台荣耀是非 root 的，不能像平板那样开 root 玩深层权限——但它有一条更稳的远程通道：**Tailscale**。这篇文章记录从「理论」到「真机跑通」的整个过程，包括一个让我有点意外的发现，和一个**对理论篇的重要推倒**。

## 一、为什么非 root 主力机也能被遥控

主力机没法 root，很多教程上的"骚操作"用不了。但遥控手机这件事，**90% 的日常操作走 ADB 就够了**，不需要 root。关键卡点其实是**怎么稳定连上**：

- 手机"无线调试"用的是**随机端口**，还要求连 WiFi（国产 ROM 没连 WiFi 时这开关直接置灰）。
- 手机 IP 是 DHCP 租的，会漂移，甚至跟家里 Windows 台式机撞车。

两个都不稳，AI 想"随手"连上就难。**Tailscale 恰好解决这两个**：它在手机和服务器之间拉一条虚拟局域网，手机拿到固定的 `100.x` 虚拟 IP，端口我们能自己固定成 5555，且**不依赖 WiFi**（用流量也能连）。

```
┌─ 服务器/NAS ────────────────┐
│  Hermes Agent + adb          │
│    └→ 跨通道连接 + 自动重连     │
└──────────────┬───────────────┘
               │ Tailscale 虚拟局域网
               ▼
┌─ 荣耀主力机 (非root) ────────┐
│  固定 IP + 固定端口 5555       │
│  支付宝/淘宝已登录              │
└──────────────────────────────┘
```

## 二、打通跨网 ADB：固定 IP + 固定端口 + 自动重连

**第一步**，让 adbd 监听固定端口：

```bash
adb tcpip 5555        # 或 setprop service.adb.tcp.port 5555
```

这里有个必须记住的**坑**：`service.adb.tcp.port` 不带 `persist` 前缀，**手机重启后 adbd 会回 USB 模式，5555 消失**。所以光"固定端口"不够，还得有重连兜底。

**第二步**，host 端做一个"自动发现端口再连"的脚本。因为手机重启后，虽然 5555 没了，但"无线调试"开关和 RSA 授权都保留——**只是端口会变**。脚本先试固定 5555，不通就去扫无线调试的随机端口段，连上为止：

```python
# 伪逻辑：先试5555 → 不通则并发扫 37000-40400 随机端口 → connect 并验证 device
for p in [5555] + range(37000, 40400, 2):
    if port_open(p) and adb_connect(f"<手机TS-IP>:{p}") == "device":
        return p
```

实测：`adb connect <手机TS-IP>:5555` 返回 `device`，读电量 42%、抓到前台是 QQ——**不是假连，命令真能跑**。这条链路活了，AI 就能像碰平板一样碰主力机。

## 三、实战①：隔空定闹钟（有个小惊喜）

定闹钟最直接的方案是系统广播 `ACTION_SET_ALARM`。但荣耀的时钟包名不是通用的 `com.android.deskclock`，而是 **`com.hihonor.deskclock`**。真正执行的是它的 `com.android.alarmclock.MiddleActivity`。

我用标准契约带 `SKIP_UI` 参数试了一下：

```bash
adb shell am start -a android.intent.action.SET_ALARM \
  --ei android.intent.extra.alarm.HOUR 20 \
  --ei android.intent.extra.alarm.MINUTES 18 \
  --es android.intent.extra.alarm.MESSAGE "备注" \
  --ez android.intent.extra.alarm.SKIP_UI true
```

**惊喜来了**：荣耀 MagicOS 对 `SKIP_UI=true` 直接**静默创建了闹钟**——不需要我在手机上点任何确认，也不设成"每天"（只响一次）。打开时钟 App 一看，列表里稳稳躺着「8 分钟后响铃」。

这其实**推翻了理论篇的一个说法**：我之前在理论笔记里写，`ACTION_SET_ALARM` 只能"预填时间 + 用户手动点确认"。但配上荣耀的 `SKIP_UI`，同一契约能达到**完全无人干预**。不同 ROM 行为不一样，碰到什么是什么。

## 四、实战②：隔空看淘宝还有几个快递

这个最"生活"。让 AI 打开淘宝看还剩几个包裹：

```bash
adb shell monkey -p com.taobao.taobao -c android.intent.category.LAUNCHER 1   # 启动（别猜死Activity，用launcher入口最稳）
adb shell uiautomator dump /sdcard/ui.xml                                     # 摸屏
# 解析底部Tab → 点「我的淘宝」 → 找 content-desc="待收货 2"
```

一个**小坑**：淘宝"我的淘宝"页的待收货数量藏在 `content-desc` 里（不是 `text`），解析时两个都要抓。读出来是「**待收货 2**」——点进快递页，一个是韵达（自喷漆）已揽收在途，一个是极兔（酒精湿巾）还在等揽收。**2 个包裹，一个在路上，一个今晚才发货**。

## 五、实战③：主力机版查电费脚本

把之前平板那套查电费，移植到主力机。脚本在 `/vol1/1000/claw/电费查询/query_electricity_phone.py`：

```bash
python3 query_electricity_phone.py                 # 查询并打印
python3 query_electricity_phone.py --threshold 20  # 余额<20 exit=2 告警
python3 query_electricity_phone.py --out x.json    # 另存 JSON
```

实测输出（户号已打码）：

```json
{
  "balance": "6.76",
  "account": "****",
  "company": "南京供电公司",
  "debt": "无欠费",
  "as_of": "2026-08-31 07:30:44",
  "ok": true
}
```

**又是一个坑**：支付宝"生活缴费"页是**懒加载**——`uiautomator dump` 第一屏常常只抓到页面标题和几个图标，"查看电费 / 余额"这些条目要 **等 2-4 秒**才渲染出来。如果脚本一上来就找"查看电费"，直接扑空。

解法是**轮询等待**，并且用"首页特征"（有搜索/扫一扫）区分"首页 vs 生活缴费页标题"，避免把生活缴费页顶部标题误当入口去点：

```python
def goto_life_fee(max_try=8):
    for i in range(max_try):
        dump()
        if 命中("查看电费" or "余额(元)" or "缴费账单"): return True   # 已到位
        if is_home_page(texts):   # 首页才找入口
            tap("生活缴费", 只选 y>500 的入口卡片)
        time.sleep(2)             # 生活缴费页仍在懒加载 → 等重试
    return False
```

## 六、对理论篇的一个重要推倒：Shizuku 并不能让 adb 重启自保持

这一条最想记下来。我之前的理论笔记里写：非 root 手机可以用 **Shizuku** 写入 `persist.service.adb.tcp.port`，让重启后 5555 仍开启。**实测证明这是错的**：

1. 非 root 手机 `adb shell setprop persist.service.adb.tcp.port 5555` → 直接报 `Failed to set property`（SELinux 拒绝 shell 用户写 `persist.*` 属性）。
2. **Shizuku 的权限上限就是 adb 授权（shell 级）**，不是 root——它同样写不进 `persist.*`。
3. Shizuku 官方 issue #2044 也明确：Shizuku **不能主动利用一个持久端口**，得靠外部机制来跑 `adb tcpip` + 启动它。

**结论**：单装一个 Shizuku，**不会**自动让 adb 重启后保持在线。真要"重启后 5555 自动固定"，得靠 **Automate / Tasker** 这类开机自启 flow（激活无线调试 + 切 TCP 5555 + 启动 Shizuku），要装 2 个 App + 手机端配 flow。

**更务实的替代**：不追求 adbd 侧固定 + 重启自动，改用 **host 端自动发现端口重连**（方案二），零安装、零权限依赖，已经跑通。省事，还不用碰 App 权限。

## 踩坑总表（主力机跨网 ADB）

| # | 现象 | 原因 | 解法 |
|---|------|------|------|
| 1 | `setprop persist...` 报 Failed | 非 root shell 写不进 persist 属性 | Shizuku 也不行；改 host 端自动重连 |
| 2 | `adb tcpip` 重启失效 | `service.adb.tcp.port` 无 persist 前缀 | 接受；配 host 自动发现端口 |
| 3 | 淘宝启动报 `Error type 3` | Activity 路径随版本变 | 用 `monkey -c LAUNCHER` 取入口 |
| 4 | "待收货"数抓不到 | 藏在 `content-desc` 非 `text` | 解析时同时抓 content-desc |
| 5 | 生活缴费页无"查看电费" | 页面懒加载 | 轮询等待 + is_home_page 区分 |

## 结尾

从「AI 只能跟你打字聊天」到「AI 能替你定闹钟、查快递、查电费」，中间隔的其实就是一条**稳定的远程通道**。平板走 WiFi ADB 是局域网玩法，主力机加 Tailscale 才真正让 AI 变成了能"碰物理世界"的手脚——而且不用 root，不用装一堆 App。

那篇理论笔记里我说"后续实践结果将另文记录"，现在实践来了，还顺手把理论里那个 Shizuku 的说法纠了个错。**折腾的意义，就在于把一个东西从"我以为"变成"我验证过"。**
