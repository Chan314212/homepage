---
title: 平板自动查电费：ADB 读屏与点击的艺术
date: 2026-08-21
tags: [自动化, ADB, Android, 折腾]
summary: 户主手机号把网页版和接口方案都堵住后，我用一台已登录支付宝的 Android 平板，通过 WiFi ADB 读 UI 树、模拟点击，做出了一套无人值守的电费查询脚本。
---

我想让 NAS 定期检查家里的电费余额：低于阈值就提醒，而不是每隔几天手动打开 App 看一眼。

常规方案很快卡住了。网上的接口和网页脚本，大多要求户主手机号验证；验证码收不到，后面的代码写得再漂亮也没有用。家里那台联想平板倒是已经登录过支付宝，也绑定了电费户号。既然登录态现成，最省事的办法就是让 NAS 直接遥控平板。

最终方案很朴素：**NAS 通过 WiFi ADB 控制平板，打开支付宝，读取界面上的余额，再输出 JSON。**

## 整体结构

```text
NAS
  Python 脚本 + platform-tools adb
      └─ 唤醒屏幕 → 启动支付宝 → 导航 → 读取余额
                         └─ JSON → 阈值判断 → 告警
                         WiFi ADB
                              ↓
联想平板 TB378FC
  支付宝已登录，已绑定电费户号
```

它的核心不是 OCR，而是“看一步、点一步”：每次操作前先导出当前页面的 UI 树，找到目标文字和坐标，再点击；页面变化后重新读取，不能假设下一步一定会出现在哪里。

## 先把无线 ADB 配好

Android 11 之后，无线调试使用随机端口，而且第一次需要配对。系统自带的 ADB 如果太旧，甚至不支持 `adb pair`。我的环境里 Debian 自带的是 29.0.6，换成新版 platform-tools 后才正常：

```bash
adb pair 192.168.2.102:44631 403627
# Successfully paired ...
adb connect 192.168.2.102:37937
# connected ...
```

配对端口和日常连接端口不是同一个。配对弹窗里的端口只用于配对，平板无线调试页面显示的端口才是之后 `adb connect` 使用的端口。

这里还有两个容易误判的问题：

- 配对码有时效，`protocol fault` 不一定是 ADB 版本问题，也可能只是配对码过期；
- DHCP 地址会变化，设备显示的地址不一定还是脚本上次保存的地址，脚本需要做自动发现或至少允许配置多个候选地址。

## 黑屏时，脚本可能在“假成功”

唤醒和解锁不能只执行命令，还要检查结果：

```bash
adb shell input keyevent KEYCODE_WAKEUP
adb shell wm dismiss-keyguard
adb shell dumpsys display | grep 'Display State='
# Display State=ON
```

最容易踩的坑是：屏幕灭着时，`uiautomator dump` 仍然能导出 UI 树，甚至点击命令也会返回成功。脚本看起来走完了，实际上是在黑屏上盲点。

因此每次查询前都要验证屏幕状态。亮屏也不等于解锁，锁屏界面同样可能有完整的 UI 树。对没有锁屏密码的设备，可以用 `wm dismiss-keyguard`；有密码或生物识别时，需要把解锁作为人工前置条件，不能假装无人值守。

## `uiautomator dump` 就是这套方案的眼睛

```bash
adb shell uiautomator dump /sdcard/ui.xml
adb shell cat /sdcard/ui.xml
```

导出的 XML 里通常有控件的 `text` 和 `bounds`：

```xml
<node text="查看电费" bounds="[330,1612][788,1694]" .../>
<node text="余额(元)" bounds="[180,1020][382,1054]" .../>
```

脚本解析文本和坐标，计算控件中心点，再执行：

```bash
adb shell input tap X Y
```

这比 OCR 更轻，也更适合按钮和标签都来自标准 Android 控件的页面。缺点是，遇到 Canvas 绘制、图片文字或完全没有语义标签的控件，UI 树就帮不上忙了。

## 导航：每一步都重新确认页面

支付宝会弹广告，页面也可能因版本变化而改变位置，所以流程不能写成固定坐标连点。核心逻辑大致是：

```python
while not reached_target_page:
    xml = dump_ui()
    nodes = parse(xml)
    close_ad_if_present(nodes)
    if contains(nodes, "生活缴费"):
        tap(node("生活缴费"))
    elif contains(nodes, "查看电费"):
        tap(node("查看电费"))
    else:
        retry_or_fail()
```

最终页面里，先定位“余额(元)”标签，再找它附近的数字。与此同时抓取截至时间、缴费单位和欠费状态，输出时保留结构化字段，后续接告警比直接返回一段文字可靠。

## 踩过的坑

| 现象 | 原因 | 解法 |
|---|---|---|
| `adb pair` 不存在 | 系统 ADB 太旧 | 使用新版 platform-tools |
| `protocol fault` | 配对码过期，或看错 IP | 重新生成配对码并确认地址 |
| 设备连接不上 | DHCP 地址变化 | 自动发现或维护候选地址 |
| 命令成功但结果错误 | 屏幕其实是 OFF | 检查 `Display State=ON` |
| `KEYCODE_SLEEP` 不生效 | ROM 行为不同 | 改用 `KEYCODE_POWER`，并验证状态 |
| 页面识别失败 | 标题和入口文字会变化 | 同时匹配多个页面特征 |
| 查询中途息屏 | 系统休眠时间太短 | 查询期间临时常亮，结束后恢复 |

## 最终脚本

脚本位于 `/vol1/1000/claw/电费查询/query_electricity.py`：

```bash
python3 query_electricity.py
python3 query_electricity.py --threshold 20
```

第二种写法在余额低于 20 时返回退出码 2，方便接定时任务和告警。脚本还会尽量恢复设备原来的亮屏、休眠状态，避免一次查询改变平板的日常使用习惯。

示例输出中的户号已脱敏：

```json
{
  "balance": "5.54",
  "as_of": "2026-08-21 07:30:43",
  "account": "*************",
  "company": "南京供电公司",
  "debt": "无欠费",
  "ok": true
}
```

## 这套方法还能做什么

只要一个 App 的操作能够通过界面完成，基本都可以套用这套模式：`dump` 是眼睛，`tap` 是手指，解析规则负责判断下一步。查话费、抓首页标题、做简单签到，都可以从同一个骨架开始。

它当然不是万能方案。UI 一改版，定位规则就可能失效；设备断网、锁屏、弹窗，也都需要脚本处理。可在没有开放 API、又已经有登录态的情况下，ADB 往往是成本最低的曲线救国方案。

折腾的乐趣，有时就是把一个原本只能手动完成的动作，拆成一串自己能理解的步骤。
