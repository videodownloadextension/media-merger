"""
PyInstaller 打包脚本
用于将程序打包成单个可执行文件，并包含 ffmpeg
"""

import os
import shutil
import sys
import subprocess

def build_exe():
    """打包程序"""
    
    # 检查 PyInstaller 是否安装
    try:
        import PyInstaller
    except ImportError:
        print("正在安装 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # 下载 ffmpeg（如果不存在）
    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    ffmpeg_zip = "ffmpeg.zip"
    ffmpeg_exe = "ffmpeg.exe"
    
    if not os.path.exists(ffmpeg_exe):
        print("正在下载 ffmpeg...")
        import urllib.request
        import zipfile
        
        # 下载 ffmpeg
        print(f"从 {ffmpeg_url} 下载...")
        urllib.request.urlretrieve(ffmpeg_url, ffmpeg_zip)
        
        # 解压
        print("正在解压 ffmpeg...")
        with zipfile.ZipFile(ffmpeg_zip, 'r') as zip_ref:
            zip_ref.extractall("ffmpeg_temp")
        
        # 查找 ffmpeg.exe
        for root, dirs, files in os.walk("ffmpeg_temp"):
            if "ffmpeg.exe" in files:
                shutil.copy(os.path.join(root, "ffmpeg.exe"), "ffmpeg.exe")
                break
        
        # 清理临时文件
        shutil.rmtree("ffmpeg_temp")
        os.remove(ffmpeg_zip)
        print("ffmpeg 下载完成")
    
    # 打包命令
    cmd = [
        "pyinstaller",
        "--onefile",                    # 打包成单个文件
        "--windowed",                   # 无控制台窗口
        "--name", "音视频合并工具",      # 程序名称
        "--icon", "icon.ico" if os.path.exists("icon.ico") else None,  # 图标（可选）
        "--add-data", f"ffmpeg.exe{os.pathsep}.",  # 添加 ffmpeg
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.scrolledtext",
        "--clean",                      # 清理临时文件
        "media_merger.py"               # 主程序文件
    ]
    
    # 移除 None 参数
    cmd = [c for c in cmd if c is not None]
    
    print("正在打包程序...")
    subprocess.check_call(cmd)
    
    print("\n✅ 打包完成！")
    print(f"可执行文件位于：dist/音视频合并工具.exe")
    print("\n提示：")
    print("1. 可以将 dist 目录下的 exe 文件复制到任何地方运行")
    print("2. 程序已包含 ffmpeg，无需单独安装")
    print("3. 配置文件保存在用户目录的 .media_merger 文件夹中")

if __name__ == "__main__":
    build_exe()
