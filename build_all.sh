#!/bin/bash
# 一键重建站点：折腾笔记 → 读书笔记 → sitemap
# 图标与分享图改动较少，需要时单独跑 python3 gen_assets.py
# 用法: ./build_all.sh
set -e
cd "$(dirname "$0")"

echo "▶ 构建折腾笔记…"
python3 build_notes.py
echo "▶ 构建读书笔记…"
python3 build_reading.py
echo "▶ 生成 sitemap…"
python3 build_sitemap.py

echo "✅ 构建完成。本地预览：./preview.sh　确认无误后：git push 上线"
