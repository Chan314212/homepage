#!/bin/bash
# 个人主页本地预览：改完先看效果，OK 再 push（EdgeOne 自动部署）
# 用法:
#   ./preview.sh          # 启动预览（默认端口 8888）
#   ./preview.sh 8890     # 指定端口
#   ./preview.sh stop     # 停止预览
# 浏览器打开 http://192.168.2.104:<端口> ，改文件后 F5 刷新即可

PORT=${1:-8888}
cd "$(dirname "$0")"

if [ "$1" = "stop" ]; then
  if [ -f .preview.pid ]; then
    kill "$(cat .preview.pid)" 2>/dev/null
    rm -f .preview.pid
    echo "预览已停止"
  else
    echo "没有正在运行的预览"
  fi
  exit 0
fi

if [ -f .preview.pid ] && kill -0 "$(cat .preview.pid)" 2>/dev/null; then
  echo "预览已在运行: http://192.168.2.104:$PORT"
  exit 0
fi

# 端口占用检查
if ss -tln 2>/dev/null | grep -q ":$PORT "; then
  echo "端口 $PORT 被占用，换个端口试试: $0 8890"
  exit 1
fi

python3 -m http.server "$PORT" --bind 0.0.0.0 >/dev/null 2>&1 &
echo $! > .preview.pid

sleep 0.5
if kill -0 "$(cat .preview.pid)" 2>/dev/null; then
  echo "✅ 预览已启动:  http://192.168.2.104:$PORT"
  echo "   改完文件浏览器 F5 刷新即可查看"
  echo "   确认无误后 git commit && git push 上线"
  echo "   停止预览: ./preview.sh stop"
else
  echo "启动失败，检查端口或 python3"
  rm -f .preview.pid
  exit 1
fi
