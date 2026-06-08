#!/bin/bash
# 部署到群晖 NAS 的打包脚本
# 用法: ./deploy.sh <NAS_IP> [NAS_USER]
# 例如: ./deploy.sh 192.168.3.100 admin

set -e
NAS_IP="${1:-请填入NAS的IP}"
NAS_USER="${2:-admin}"  # 群晖默认是 admin，DSM 7+ 可能用本地账号

echo "▶ 1/5 构建 Kiosk 前端..."
cd kiosk && npm run build && cd ..

echo "▶ 2/5 复制前端构建产物到后端..."
rm -rf backend/kiosk_dist
cp -r kiosk/dist backend/kiosk_dist

echo "▶ 3/5 创建持久化数据目录..."
mkdir -p data

echo "▶ 4/5 生成 .env 模板（已有则跳过）..."
if [ ! -f backend/.env ]; then
  cat > backend/.env <<- ENVEOF
DINGTALK_APP_KEY=your_app_key
DINGTALK_APP_SECRET=your_app_secret
DINGTALK_AGENT_ID=your_agent_id
SERVER_BASE_URL=http://${NAS_IP}:8000
DB_PATH=parcel.db
MAX_SHELVES=2
MAX_LAYERS=4
PRINTER_NAME=HUAWEI_PixLab_V1_0409
PRINTER_HOST=${NAS_IP}
COURIER_LAYER_MAP=顺丰:1-1,中通:1-2,圆通:1-3,申通:1-4
ENVEOF
  echo "  已创建 backend/.env，请检查钉钉凭证"
fi

echo ""
echo "✅ 打包完成！上传到 NAS:"
echo "   scp -r . ${NAS_USER}@${NAS_IP}:/volume1/docker/parcel-kiosk/"
echo ""
echo "NAS SSH 里运行:"
echo "   cd /volume1/docker/parcel-kiosk && docker-compose up -d"
