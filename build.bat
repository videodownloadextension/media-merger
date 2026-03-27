@echo off
echo 正在打包音视频合并工具...
echo.

REM 安装 PyInstaller
pip install pyinstaller

REM 运行打包脚本
python build_exe.py

echo.
echo 打包完成！
pause
