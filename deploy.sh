#!/bin/bash
# 部署到群晖 NAS 的打包脚本
# 用法: ./deploy.sh <NAS_IP>  例如: ./deploy.sh 192.168.3.100

set -e
NAS_IP="${1:-请填入NAS的IP}"
NAS_USER="${2:-admin}"

echo "▶ 1/3 构建 Kiosk 前端..."
cd kiosk && npm run build && cd ..

echo "▶ 2/3 复制 Kiosk 构建文件到后端..."
rm -rf backend/kiosk_dist
cp -r kiosk/dist backend/kiosk_dist

echo "▶ 3/3 更新 docker-compose 里的 NAS IP..."
sed -i "s|http://NAS_IP:8000|http://${NAS_IP}:8000|g" docker-compose.yml

echo ""
echo "✅ 打包完成！上传到 NAS:"
echo "   scp -r . ${NAS_USER}@${NAS_IP}:/volume1/docker/parcel-kiosk/"
echo ""
echo "NAS SSH 里运行:"
echo "   cd /volume1/docker/parcel-kiosk && docker-compose up -d"
