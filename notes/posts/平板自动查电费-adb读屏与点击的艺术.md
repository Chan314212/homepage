---
title: 平板自动查电费：ADB 读屏与点击的艺术
date: 2026-08-21
tags: [自动化, ADB, Android, 折腾]
summary: 用 ADB 无线遥控一台联想平板，自动打开支付宝查电费余额。从配对到无人值守，把「读屏 + 点击」这套万能自动化套路的原理和踩坑全部写透。
---

家里的 NAS 是我日常的数字管家，有一阵子我想让它帮忙盯电费余额——不是偶尔看一眼，是那种"余额低于阈值就提醒我充值"的自动化。

最初的想法很朴素：用 ADB 控制平板打开支付宝查电费。有朋友说"用 Auto.js 就行"，确实——但那是在平板本地搭一套自动化引擎，得装 Termux、调脚本、配 cron，是第二档的玩法。当晚先干第一档：**NAS 通过 WiFi ADB 直接遥控平板**，30 分钟内跑通首查，先拿到数据再说。

这篇文章记录整个流程：原理、代码、以及四个小时里踩过的所有坑。

## 整体方案

```
┌─ NAS ──────────────────────────────┐
│  Python 脚本 + platform-tools adb    │
│    └→ 唤醒屏幕 → 开支付宝 → 导航      │
│         → 读余额 → JSON → 阈值告警    │
└──────────────┬─────────────────────┘
               │ WiFi (无线调试, 已配对)
               ▼
┌─ 联想平板 TB378FC ─────────────────┐
│  支付宝已登录、已绑定电费户号          │
│  KernelSU root（但生产固件无 adb root）│
└────────────────────────────────────┘
```

一句话原理：**脚本是个"盲人操作员"——每步先摸一遍屏幕（读 UI 树），找到目标文字和坐标，再按坐标点一下。**

## 第一步：WiFi 调试配对

Android 11+ 的"无线调试"用的是**随机端口**，不是老教程里的固定 5555，而且需要先配对。

坑一：**Debian 自带的 adb 是 29.0.6，不支持 `adb pair`**（Android 11 配对协议要 adb 30+）。下载新版 platform-tools 即可：

```bash
curl -sL -o platform-tools.zip https://dl.google.com/android/repository/platform-tools-latest-linux.zip
unzip -o -q platform-tools.zip
# 固化到系统路径, 别放 /tmp (重启会丢)
cp -r platform-tools/* /usr/local/share/platform-tools/
ln -sf /usr/local/share/platform-tools/adb /usr/local/bin/adb
```

坑二：**配对报 `protocol fault (couldn't read status message)`**。第一次遇到以为是 adb 版本问题，换了三个版本还是报错——最后发现是**配对码过期了**（Android 的配对码有时效），重新生成一次就好。这个报错极有迷惑性。

坑三：**IP 撞车**。平板上显示的 IP 是 `192.168.2.103`，但我怎么连都连不上，扫端口发现它其实在 `192.168.2.102`——因为 Windows 台式机关机了，DHCP 把 102 分给了平板。**DHCP 环境下的设备地址是会变的**，所以脚本里要做设备自动发现（见下文）。

配对成功的标志：

```bash
adb pair 192.168.2.102:44631 403627
# Successfully paired to 192.168.2.102:44631 [guid=...]
adb connect 192.168.2.102:37937
# connected to 192.168.2.102:37937
```

> 注意：配对端口和连接端口是两个！配对弹窗里的 IP:端口是临时的，无线调试主页面的"IP 地址和端口"才是日常连接用的。

## 第二步：屏幕唤醒与解锁

屏幕灭着的时候发任何点击都是白搭。先点亮、解锁、并**验证状态**：

```bash
adb shell input keyevent KEYCODE_WAKEUP   # 亮屏
adb shell wm dismiss-keyguard             # 解锁 (无锁屏密码时)
adb shell dumpsys display | grep 'Display State='
# → Display State=ON 才算真的亮了
```

坑四：**`Display State=OFF` 时 UI 树照样能 dump**——这很误导人。屏幕灭着，`uiautomator dump` 依然能抓到 Activity 的控件树，点击也照样注入，看起来"成功"了，其实是在黑屏上盲打。所以**必须显式验证屏幕状态**，别信流程"走通了"。

坑五：**亮屏 ≠ 解锁**。`KEYCODE_WAKEUP` 唤起来的是锁屏界面（特征：屏幕中间显示大号时间/日期/电量），这时候启动支付宝也不会到前台。脚本里每次查询前**无条件执行一次点亮 + 解锁**，不区分初始状态。

## 第三步：核心魔法 —— uiautomator dump

这是整套方案的心脏：

```bash
adb shell uiautomator dump /sdcard/ui.xml
adb shell cat /sdcard/ui.xml
```

Android 会把**当前屏幕所有控件**导成 XML，每个控件带 `text` 和屏幕坐标 `bounds`：

```xml
<node text="查看电费" bounds="[330,1612][788,1694]" .../>
<node text="余额(元)" bounds="[180,1020][382,1054]" .../>
<node text="5.54"     bounds="[1880,1020][2072,1056]" .../>
```

用正则把 `text + 中心坐标` 提取成清单，一行代码：

```python
nodes = re.findall(r'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
```

这就是"眼睛"。**不用 OCR，直接读控件树文本**，所以又快又准。

## 第四步：导航循环 —— 看一步，点一步

```python
# 伪代码: 每步都是 摸屏 → 找目标 → 点击 → 再摸
while 目标页没到:
    xml = dump()
    nodes = parse(xml)
    if 找到"生活缴费":  tap(它的坐标); continue
    ...
```

这跟人操作完全同构：**你看屏幕找按钮 → 手指点 → 再看下一步**。每步都带重试和超时。

支付宝爱弹广告，所以每次 dump 完先扫一遍：右上角区域出现"跳过/关闭/x"文案就先点掉，再走主流程。

## 第五步：解析余额

在最终页面的 XML 里，按节点顺序找"余额(元)"标签，它后面紧跟的数字节点就是余额：

```python
if "余额" in t and "元" in t:
    取后面第一个纯数字节点 → 5.54
```

顺手把户号（16 位数字）、截至时间、缴费单位、欠费状态都抓下来。

## 踩坑总表

| # | 现象 | 原因 | 解法 |
|---|------|------|------|
| 1 | `adb pair` 未知命令 | Debian adb 29 太老 | 装 platform-tools 37+ |
| 2 | `protocol fault` | 配对码过期 / IP 看错 | 重新生成配对码 |
| 3 | IP 连不上 | DHCP 地址变了/与 Windows 撞车 | 脚本自动发现设备 |
| 4 | 操作"成功"但结果不对 | 屏幕实际是 OFF，在黑屏盲打 | 显式验证 Display State |
| 5 | `KEYCODE_SLEEP` 不生效 | 联想 ZUI ROM 不认 | 换 `KEYCODE_POWER` 切换 |
| 6 | 页面识别失败 | 账单页标题是"缴费账单"非"生活缴费" | 放宽识别词（认"我的户号/查看电费"） |
| 7 | 查询中途屏幕灭了 | 休眠超时 120 秒，查询要 30 秒 | 查询期间强制常亮，查完恢复原值 |

## 最终脚本

`/vol1/1000/claw/电费查询/query_electricity.py`，无人值守，约 200 行 Python：

```bash
python3 query_electricity.py                  # 查询, 输出 JSON
python3 query_electricity.py --threshold 20   # 余额<20 时 exit code=2 (可接告警)
```

关键特性：

- **零 token、零人工**：纯 ADB 模拟点击
- **状态自恢复**：息屏唤醒 → 查完自动息屏；本来亮着 → 不动；休眠超时用完还原
- **设备自动发现**：已连接地址优先，断了走 mDNS 兜底
- **弹窗防御**：广告自动跳过

实测输出：

```json
{
  "balance": "5.54",
  "as_of": "2026-08-21 07:30:43",
  "account": "3200155724358",
  "company": "南京供电公司",
  "debt": "无欠费",
  "ok": true
}
```

## 这套模式的通用性

**`dump` 是眼睛，`tap` 是手指，正则是指挥官。** 这套套路不只能查电费——任何能通过 UI 完成的 App 操作（查话费、签到打卡、抓首页标题、抢券）都能照葫芦画瓢。那天顺手用同一套流程打开 B 站抓了首页四个视频标题，全程 15 秒。

至于朋友提的 Auto.js（AutoX.js）方案，原理完全一样，只是把"眼睛和手指"搬到了平板本地——NAS 断了也能自己跑。那是第二档的玩法，等哪天想再折腾一档再说。

**折腾的乐趣，在于把一个东西彻底搞明白。**
