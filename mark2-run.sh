#!/bin/bash

py_exe="~/MARK2_reisenderBackend/.venv/bin/python"
motorNode_path="~/MARK2_reisenderBackend/motorNode/run_bridge_app.py"
app_path="~/MARK2_reisenderBackend/app.py"

($py_exe) ($motorNode_path)

sleep 5

($py_exe) ($app_path)