#!/usr/bin/env python3
"""
音视频自动合并工具 - 嵌入式 ffmpeg 版本
功能：自动扫描文件夹，将相同文件名的视频和音频合并为 MP4 文件
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import threading
import subprocess
import time
import json
from datetime import datetime
from pathlib import Path

def get_resource_path(relative_path):
    """获取资源文件的绝对路径（支持 PyInstaller 打包）"""
    try:
        # PyInstaller 创建临时文件夹，将路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

class CollapsibleFrame(ttk.Frame):
    """可折叠框架组件"""
    def __init__(self, parent, text="", *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        
        self.text = text
        self.is_expanded = False
        
        # 创建标题按钮
        self.title_button = ttk.Button(
            self, 
            text=f"▶ {self.text}", 
            command=self.toggle,
            style='Collapsible.TButton'
        )
        self.title_button.pack(fill=tk.X, pady=(0, 2))
        
        # 创建内容框架
        self.content_frame = ttk.Frame(self)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 初始状态为折叠
        self.collapse()
        
    def toggle(self):
        """切换展开/折叠状态"""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()
            
    def expand(self):
        """展开内容"""
        self.is_expanded = True
        self.title_button.config(text=f"▼ {self.text}")
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
    def collapse(self):
        """折叠内容"""
        self.is_expanded = False
        self.title_button.config(text=f"▶ {self.text}")
        self.content_frame.pack_forget()

class Config:
    """配置管理类"""
    def __init__(self):
        # 配置文件路径（保存在用户目录）
        self.config_dir = Path.home() / '.media_merger'
        self.config_file = self.config_dir / 'config.json'
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        default_config = {
            'last_folder': '',
            'window_geometry': '850x750',
            'first_run': True
        }
        
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
        except Exception as e:
            print(f"加载配置文件失败：{e}")
        
        return default_config
    
    def save_config(self):
        """保存配置文件"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败：{e}")
            return False
    
    def get_last_folder(self):
        """获取上次选择的文件夹"""
        folder = self.config.get('last_folder', '')
        if folder and os.path.exists(folder):
            return folder
        return ''
    
    def set_last_folder(self, folder):
        """设置上次选择的文件夹"""
        self.config['last_folder'] = folder
        self.save_config()
    
    def get_window_geometry(self):
        """获取窗口大小"""
        return self.config.get('window_geometry', '850x750')
    
    def set_window_geometry(self, geometry):
        """设置窗口大小"""
        self.config['window_geometry'] = geometry
        self.save_config()

class SimpleMediaMerger:
    def __init__(self, root):
        self.root = root
        self.root.title("音视频自动合并工具")
        
        # 加载配置
        self.config = Config()
        
        # 设置窗口大小和位置
        geometry = self.config.get_window_geometry()
        self.root.geometry(geometry)
        
        # 获取 ffmpeg 路径（嵌入式）
        self.ffmpeg_path = self.get_ffmpeg_path()
        
        # 支持的视频格式
        self.video_exts = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        # 支持的音频格式
        self.audio_exts = {'.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma'}
        
        # 进度控制标志
        self.stop_processing = False
        # 添加进程对象变量
        self.current_process = None  # 保存当前运行的 FFmpeg 进程
        
        self.setup_ui()
        
        # 加载上次选择的文件夹
        last_folder = self.config.get_last_folder()
        if last_folder:
            self.folder_path.set(last_folder)
            self.log(f"已加载上次选择的文件夹：{last_folder}")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def get_ffmpeg_path(self):
        """获取 ffmpeg 可执行文件路径（跨平台支持）"""
        import sys
        import platform
        
        # 获取当前操作系统
        system = platform.system().lower()
        
        # 首先检查是否在打包环境中
        if getattr(sys, 'frozen', False):
            # 打包后的环境，ffmpeg 在临时目录
            if system == 'windows':
                ffmpeg_exe = get_resource_path('ffmpeg.exe')
            elif system == 'linux':
                ffmpeg_exe = get_resource_path('ffmpeg')
            elif system == 'darwin':  # macOS
                ffmpeg_exe = get_resource_path('ffmpeg')
            else:
                ffmpeg_exe = None
            
            if ffmpeg_exe and os.path.exists(ffmpeg_exe):
                return ffmpeg_exe
            
            # 也检查程序所在目录（如果用户手动放置了 ffmpeg）
            app_dir = os.path.dirname(sys.executable)
            if system == 'windows':
                ffmpeg_exe = os.path.join(app_dir, 'ffmpeg.exe')
            else:
                ffmpeg_exe = os.path.join(app_dir, 'ffmpeg')
            
            if os.path.exists(ffmpeg_exe):
                return ffmpeg_exe
        # 开发环境，检查当前目录和系统 PATH
        import shutil
        
        # 检查当前目录
        if system == 'windows':
            if os.path.exists('ffmpeg.exe'):
                return 'ffmpeg.exe'
        else:
            if os.path.exists('ffmpeg'):
                return './ffmpeg'
        
        # 检查系统 PATH
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            return ffmpeg_path
        
        # 如果都找不到，返回 None，后续会提示用户
        return None
       
    def setup_ui(self):
        """设置用户界面"""
        style = ttk.Style()
        style.configure('Collapsible.TButton', font=('Arial', 9, 'bold'))
        
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(7, weight=1)
        
        title_label = ttk.Label(main_frame, text="音视频自动合并工具", 
                                font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 15))
        
        ttk.Label(main_frame, text="选择文件夹：", font=('Arial', 10)).grid(
            row=1, column=0, sticky=tk.W, pady=5)
        
        folder_frame = ttk.Frame(main_frame)
        folder_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        folder_frame.columnconfigure(0, weight=1)
        
        self.folder_path = tk.StringVar()
        folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_path, 
                                 font=('Arial', 9))
        folder_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        browse_btn = ttk.Button(folder_frame, text="浏览", command=self.browse_folder,
                                width=8)
        browse_btn.grid(row=0, column=1)
        
        # 可折叠使用说明
        self.info_frame = CollapsibleFrame(main_frame, text="使用说明")
        self.info_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        
        info_content = ttk.Frame(self.info_frame.content_frame)
        info_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        features_text = """📋 功能特点：
• 自动扫描文件夹中的视频和音频文件
• 将相同文件名的文件配对合并（如：video.mp4 + video.mp3）
• 合并后的文件保存到原文件夹下的 merged 目录
• 如果 merged 目录中已有同名文件，将自动跳过
• 基于文件大小的准确进度显示（MB/秒，剩余时间）
• 自动记住上次选择的文件夹
• 内置 ffmpeg，无需单独安装
• 支持中途停止处理
        """
        
        features_label = ttk.Label(info_content, text=features_text, justify=tk.LEFT, 
                                   font=('Arial', 9))
        features_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        formats_text = """🎬 支持格式：
视频格式：MP4, AVI, MKV, MOV, WMV, FLV, WEBM, M4V
音频格式：MP3, WAV, AAC, FLAC, M4A, OGG, WMA
        """
        
        formats_label = ttk.Label(info_content, text=formats_text, justify=tk.LEFT,
                                  font=('Arial', 9))
        formats_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
        
        steps_text = """📖 使用步骤：
1. 点击「浏览」按钮选择包含音视频文件的文件夹
2. 点击「开始合并」按钮开始处理
3. 查看实时进度（文件大小/速度/剩余时间）
4. 可随时点击「停止」按钮取消处理
        """
        
        steps_label = ttk.Label(info_content, text=steps_text, justify=tk.LEFT,
                                font=('Arial', 9))
        steps_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 10))
        
        notes_text = """⚠️ 注意事项：
• 确保视频和音频文件名相同（不包括扩展名）
• 本程序已内置 ffmpeg，无需额外安装
• 处理过程中请勿关闭程序或删除源文件
• 进度基于文件大小估算，最终文件可能略有误差
        """
        
        notes_label = ttk.Label(info_content, text=notes_text, justify=tk.LEFT,
                                font=('Arial', 9), foreground='orange')
        notes_label.grid(row=3, column=0, sticky=tk.W)
        
        # 进度显示区域
        progress_frame = ttk.LabelFrame(main_frame, text="处理进度", padding="10")
        progress_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
        progress_frame.columnconfigure(0, weight=1)
        
        self.total_progress_label = ttk.Label(progress_frame, text="总体进度：0/0 (0%)")
        self.total_progress_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.total_progress = ttk.Progressbar(progress_frame, mode='determinate', length=550)
        self.total_progress.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.current_file_label = ttk.Label(progress_frame, text="当前文件：等待开始")
        self.current_file_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        
        self.current_progress = ttk.Progressbar(progress_frame, mode='determinate', length=550)
        self.current_progress.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.progress_detail = ttk.Label(progress_frame, text="", font=('Arial', 8))
        self.progress_detail.grid(row=4, column=0, sticky=tk.W, pady=(0, 0))
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, pady=(0, 10))
        
        self.start_btn = ttk.Button(button_frame, text="开始合并", 
                                     command=self.start_merge, width=12)
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = ttk.Button(button_frame, text="停止", 
                                    command=self.stop_merge, width=12, state='disabled')
        self.stop_btn.grid(row=0, column=1, padx=5)
        
        self.clear_btn = ttk.Button(button_frame, text="清空日志", 
                                    command=self.clear_log, width=12)
        self.clear_btn.grid(row=0, column=2, padx=5)
        
        self.exit_btn = ttk.Button(button_frame, text="退出", 
                                   command=self.on_closing, width=12)
        self.exit_btn.grid(row=0, column=3, padx=5)
        
        # 状态栏
        self.status_label = ttk.Label(main_frame, text="就绪", relief=tk.SUNKEN, 
                                       anchor=tk.W, font=('Arial', 9))
        self.status_label.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.last_log_label = ttk.Label(main_frame, text="", font=('Arial', 8), 
                                         foreground='gray', anchor=tk.W)
        self.last_log_label.grid(row=7, column=0, sticky=tk.W, pady=(0, 5))
        
        # 可折叠处理日志
        self.log_frame = CollapsibleFrame(main_frame, text="处理日志")
        self.log_frame.grid(row=8, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        main_frame.rowconfigure(8, weight=1)
        self.log_frame.content_frame.columnconfigure(0, weight=1)
        self.log_frame.content_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame.content_frame, 
            height=12, 
            width=80,
            font=('Consolas', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def browse_folder(self):
        """浏览文件夹"""
        folder = filedialog.askdirectory(initialdir=self.folder_path.get() or os.path.expanduser("~"))
        if folder:
            self.folder_path.set(folder)
            self.config.set_last_folder(folder)
            self.log(f"已选择文件夹：{folder}")
            
    def on_closing(self):
        """窗口关闭事件"""
        geometry = self.root.geometry()
        self.config.set_window_geometry(geometry)
        self.root.quit()
        self.root.destroy()
            
    def log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        
        self.last_log_label.config(text=f"📝 {message[:80]}")
        
        if not self.log_frame.is_expanded:
            self.last_log_label.config(foreground='blue')
            self.root.after(2000, lambda: self.last_log_label.config(foreground='gray'))
        
        self.root.update()
        
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        self.last_log_label.config(text="")
        
    def stop_merge(self):
        """停止合并处理"""
        self.stop_processing = True
        self.log("⚠️ 正在停止处理...")
        self.status_label.config(text="正在停止...")
        # 强制终止 FFmpeg 进程
        if self.current_process and self.current_process.poll() is None:
            try:
                # Windows 系统
                if os.name == 'nt':
                    # 使用 taskkill 强制终止进程树
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.current_process.pid)], 
                                 capture_output=True)
                else:
                    # Linux/macOS
                    self.current_process.terminate()
                    time.sleep(1)
                    if self.current_process and self.current_process.poll() is None:
                        self.current_process.kill()
                self.log("✅ 已强制停止 FFmpeg 进程")
            except Exception as e:
                self.log(f"⚠️ 停止进程时出错：{e}")

        
    def update_total_progress(self, current, total):
        """更新总体进度"""
        if total > 0:
            percentage = (current / total) * 100
            self.total_progress_label.config(text=f"总体进度：{current}/{total} ({percentage:.1f}%)")
            self.total_progress['value'] = percentage
        self.root.update()
        
    def update_current_progress(self, percent, detail=""):
        """更新当前文件进度"""
        self.current_progress['value'] = percent
        if detail:
            self.progress_detail.config(text=detail)
        self.root.update()
        
    def update_current_file(self, filename, index, total):
        """更新当前正在处理的文件"""
        self.current_file_label.config(text=f"当前文件 [{index}/{total}]：{filename}")
        self.current_progress['value'] = 0
        self.progress_detail.config(text="")
        self.root.update()
        
    def estimate_output_size(self, video_path, audio_path):
        """估算输出文件大小"""
        try:
            video_size = os.path.getsize(video_path)
            audio_size = os.path.getsize(audio_path)
            estimated = video_size + (audio_size * 0.7)
            self.log(f"   📊 预估输出大小：{estimated/(1024*1024):.1f} MB")
            return estimated
        except Exception as e:
            self.log(f"   ⚠️ 无法估算文件大小，使用默认值")
            return 100 * 1024 * 1024
    
    def merge_with_progress(self, video_path, audio_path, output_path):
        """使用 FFmpeg 合并，基于文件大小显示进度（编码修复版）"""
        try:
            if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
                return False, "未找到 ffmpeg，请确保程序完整安装"
            
            estimated_size = self.estimate_output_size(video_path, audio_path)
            
            cmd = [
                self.ffmpeg_path,
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                '-y',
                output_path
            ]
            
            # 使用二进制模式避免编码问题
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self.current_process = process
            
            start_time = datetime.now()
            
            # 读取 stdout 的线程
            def read_stdout():
                for line_bytes in iter(process.stdout.readline, b''):
                    try:
                        # 尝试 UTF-8 解码
                        line = line_bytes.decode('utf-8', errors='ignore')
                    except:
                        # 如果失败，使用 GBK
                        try:
                            line = line_bytes.decode('gbk', errors='ignore')
                        except:
                            line = line_bytes.decode('latin-1', errors='ignore')
                    self.process_ffmpeg_output(line)
                process.stdout.close()
            
            def read_stderr():
                for line_bytes in iter(process.stderr.readline, b''):
                    # 不显示 stderr，避免干扰
                    pass
            
            import threading
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()
            
            # 监控文件大小进度
            while process.poll() is None and not self.stop_processing:
                if os.path.exists(output_path):
                    current_size = os.path.getsize(output_path)
                    if estimated_size > 0:
                        percent = (current_size / estimated_size) * 100
                        percent = min(percent, 99.5)
                        
                        elapsed = (datetime.now() - start_time).total_seconds()
                        if elapsed > 0 and current_size > 0:
                            speed = current_size / (1024 * 1024) / elapsed
                            if speed > 0:
                                remaining_size = max(0, estimated_size - current_size)
                                remaining_seconds = remaining_size / (1024 * 1024) / speed
                                remaining_minutes = int(remaining_seconds // 60)
                                remaining_secs = int(remaining_seconds % 60)
                                
                                detail = (f"📦 {percent:.1f}% | "
                                        f"{current_size/(1024*1024):.1f}/{estimated_size/(1024*1024):.1f} MB | "
                                        f"⚡ {speed:.1f} MB/s | "
                                        f"⏱️ 剩余 {remaining_minutes}:{remaining_secs:02d}")
                            else:
                                detail = (f"📦 {percent:.1f}% | "
                                        f"{current_size/(1024*1024):.1f}/{estimated_size/(1024*1024):.1f} MB")
                        else:
                            detail = (f"📦 {percent:.1f}% | "
                                    f"{current_size/(1024*1024):.1f}/{estimated_size/(1024*1024):.1f} MB")
                        
                        self.update_current_progress(percent, detail)
                
                time.sleep(0.3)
            
            # 等待进程结束
            process.wait()
            
            if os.path.exists(output_path) and not self.stop_processing:
                final_size = os.path.getsize(output_path)
                elapsed = (datetime.now() - start_time).total_seconds()
                detail = f"✅ 完成！{final_size/(1024*1024):.1f} MB | 耗时 {elapsed:.1f}秒"
                self.update_current_progress(100, detail)
            
            if process.returncode == 0:
                return True, "成功"
            else:
                return False, "FFmpeg 处理失败"
                    
        except Exception as e:
            return False, str(e)
        finally:
            # 清理进程对象
            self.current_process = None

    def process_ffmpeg_output(self, line):
        """处理 FFmpeg 输出行"""
        line = line.strip()
        
        # 解析速度，更新进度详情
        if line.startswith('speed='):
            try:
                speed_str = line.split('=')[1].replace('x', '')
                speed = float(speed_str)
                # 可以在这里更新速度显示，但主要进度已经由文件大小监控处理
            except:
                pass
    def scan_and_match_files(self, folder):
        """扫描文件夹并匹配相同文件名的音视频文件"""
        videos = {}
        audios = {}
        
        for file in os.listdir(folder):
            file_path = os.path.join(folder, file)
            if os.path.isfile(file_path):
                name, ext = os.path.splitext(file)
                ext_lower = ext.lower()
                
                if ext_lower in self.video_exts:
                    videos[name] = file_path
                elif ext_lower in self.audio_exts:
                    audios[name] = file_path
        
        matches = []
        common_names = set(videos.keys()) & set(audios.keys())
        
        for name in common_names:
            matches.append({
                'name': name,
                'video': videos[name],
                'audio': audios[name]
            })
            
        return matches, videos, audios
    
    def check_existing_output(self, output_dir, base_name):
        """检查输出文件是否已存在"""
        output_filename = f"{base_name}.mp4"
        output_path = os.path.join(output_dir, output_filename)
        
        if os.path.exists(output_path):
            return True, output_path, output_filename
        return False, output_path, output_filename
    
    def process_merge(self):
        """执行合并处理"""
        folder = self.folder_path.get()
        
        if not folder:
            self.log("❌ 请先选择文件夹！")
            messagebox.showwarning("警告", "请先选择文件夹！")
            return
            
        if not os.path.exists(folder):
            self.log(f"❌ 文件夹不存在：{folder}")
            return
        
        self.stop_processing = False
        self.log("=" * 60)
        self.log(f"开始处理文件夹：{folder}")
        
        # 扫描并匹配文件
        self.log("📁 正在扫描文件...")
        matches, videos, audios = self.scan_and_match_files(folder)
        
        self.log(f"📹 找到 {len(videos)} 个视频文件")
        self.log(f"🎵 找到 {len(audios)} 个音频文件")
        
        if not matches:
            self.log("❌ 没有找到相同文件名的音视频配对！")
            messagebox.showwarning("警告", "没有找到相同文件名的音视频配对！\n请确保视频和音频文件名相同（不包括扩展名）")
            self.update_total_progress(0, 0)
            return
        
        self.log(f"🔍 找到 {len(matches)} 对匹配的文件：")
        for match in matches:
            self.log(f"   • {match['name']}")
        
        # 创建输出目录
        output_dir = os.path.join(folder, "merged")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.log(f"✅ 创建输出目录：{output_dir}")
        
        # 检查已存在的文件
        self.log("\n🔍 检查已存在的输出文件...")
        to_process = []
        skipped = []
        
        for match in matches:
            exists, output_path, output_filename = self.check_existing_output(output_dir, match['name'])
            if exists:
                skipped.append(match)
                self.log(f"   ⏭️  跳过 {match['name']} - 文件已存在")
            else:
                to_process.append({**match, 'output_path': output_path, 'output_filename': output_filename})
        
        if skipped:
            self.log(f"\n⏭️  跳过 {len(skipped)} 个已存在的文件")
        
        if not to_process:
            self.log("✅ 所有文件都已处理完成！")
            messagebox.showinfo("完成", f"所有 {len(matches)} 个文件都已存在！")
            self.update_total_progress(0, 0)
            return
        
        self.log(f"\n📊 需要处理：{len(to_process)} 个文件")
        self.update_total_progress(0, len(to_process))
        
        # 开始合并
        success_count = 0
        for i, match in enumerate(to_process, 1):
            if self.stop_processing:
                self.log("\n⚠️ 用户停止了处理")
                break
                
            self.update_current_file(match['name'], i, len(to_process))
            self.log(f"\n🔄 [{i}/{len(to_process)}] 处理：{match['name']}")
            self.log(f"   📹 视频：{os.path.basename(match['video'])}")
            self.log(f"   🎵 音频：{os.path.basename(match['audio'])}")
            
            success, message = self.merge_with_progress(
                match['video'], 
                match['audio'], 
                match['output_path']
            )
            
            if success:
                file_size = os.path.getsize(match['output_path']) / (1024 * 1024)
                self.log(f"   ✅ 成功！文件大小：{file_size:.2f} MB")
                success_count += 1
            else:
                self.log(f"   ❌ 失败：{message}")
            
            self.update_total_progress(i, len(to_process))
        
        self.current_file_label.config(text="当前文件：处理完成")
        self.update_current_progress(100, "")
        
        self.log("\n" + "=" * 60)
        self.log(f"✅ 处理完成！")
        self.log(f"   成功：{success_count}/{len(to_process)} 个文件")
        self.log(f"   跳过：{len(skipped)} 个已存在文件")
        self.log(f"   总计：{len(matches)} 对文件")
        
        result_msg = f"合并完成！\n成功：{success_count}/{len(to_process)} 个新文件\n跳过：{len(skipped)} 个已存在文件"
        if success_count == len(to_process):
            messagebox.showinfo("完成", result_msg)
        elif success_count > 0:
            messagebox.showwarning("完成", result_msg + "\n\n部分文件处理失败，请查看日志详情。")
        else:
            messagebox.showerror("错误", "所有文件处理失败！\n请查看日志了解详细错误信息。")
        
    def start_merge(self):
        """在新线程中开始合并"""
        if not self.folder_path.get():
            messagebox.showwarning("警告", "请先选择文件夹！")
            return
            
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_label.config(text="正在处理中...")
        
        self.total_progress['value'] = 0
        self.current_progress['value'] = 0
        self.progress_detail.config(text="")
        
        thread = threading.Thread(target=self.process_merge)
        thread.daemon = True
        thread.start()
        
        self.check_thread(thread)
        
    def check_thread(self, thread):
        """检查线程是否完成"""
        if thread.is_alive():
            self.root.after(100, lambda: self.check_thread(thread))
        else:
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.status_label.config(text="就绪")

def main():
    root = tk.Tk()
    app = SimpleMediaMerger(root)
    root.mainloop()

if __name__ == "__main__":
    main()
