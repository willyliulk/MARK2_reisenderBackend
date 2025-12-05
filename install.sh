#!/bin/bash

# # 檢查是否在 ~/pythonbackend/ 目錄下
# if [[ "$PWD" != "$HOME/pythonbackend" ]]; then
#     echo "[error] place the folder at Desktop"
#     exit 1
# fi

# apt install python3.9 venv

# pip install -r requirement.txt

# # 複製 reisender-backend.service 到 systemd
# cp reisender-backend.service /etc/systemd/system/
# # 啟動 systemd 服務
# systemctl daemon-reload
# systemctl start reisender-backend.service
# systemctl enable reisender-backend.service

# # 複製 logrotate.d-reisender-backend 到 logrotate.d
# cp logrotate.d-reisender-backend /etc/logrotate.d/
# # 執行 logrotate
# logrotate -f /etc/logrotate.d/logrotate.d-reisender-backend

# echo "Script completed successfully."


# if [[ "$PWD" != "$HOME/MARK2_reisenderBackend" ]]; then
#     echo "[error] place the folder at HOME"
#     echo "$PWD"
#     echo "$HOME/MARK2_reisenderBackend"
#     exit 1
# fi


#curl -LsSf https://astral.sh/uv/install.sh | sh

#uv sync

sudo cp mark2-app.service /etc/systemd/system/
sudo cp mark2-pico-bridge.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl start mark2-app.service
sudo systemctl enable mark2-app.service
sudo systemctl start mark2-pico-bridge.service
sudo systemctl enable mark2-pico-bridge.service

sudo cp mark2-services /etc/logrotate.d/
sudo logrotate -f /etc/logrotate.d/mark2-services
sudo usermod -a -G dialout ubuntu

echo "Script completed successfully."
