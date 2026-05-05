# 🚦 十字路口交通仿真系统 (OS 进程管理项目)

基于 Python 多线程与信号量机制的十字路口交通调度模拟。核心解决多方向车辆并发通行、红绿灯周期切换以及特种车辆（消防车、救护车、警车）优先通行的同步与互斥问题。

## ✨ 核心特性

- **多线程调度**：三条守护线程（信号灯循环 / 车辆生成 / 调度循环）并发运行，真实模拟交通场景。
- **经典同步机制**：`RLock`、`Condition`、`Semaphore` 解决资源竞争，Round‑Robin 车道扫描避免饥饿。
- **特权优先级**：急救车、消防车、警车无视红灯直接通行，不受 FIFO 排队限制。
- **双前端展示**：
  - 🖥️ **控制台模式**：基于 Rich 库的实时动态面板，彩色信号灯、排队柱状图、事件流。
  - 🌐 **Web 模式**：Gradio 可视化面板，参数滑块实时调节，大屏监控视图。
- **后端验证模式**：无 UI 静默运行，自动断言闯红灯 / FIFO 违规，适合 CI 或教学验收。

## 🛠️ 快速运行

### 1. 创建虚拟环境

Python 3.8+，在项目根目录执行：

**Windows:**
```
python -m venv .venv
.\.venv\Scripts\activate
```

**macOS / Linux:**
```
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```
pip install -r requirements.txt
```

Web 模式需要额外安装 Gradio（详见 `requirements.txt` 注释）。

### 3. 启动

```
python run.py
```

出现交互式菜单：

1. **控制台模式** — Rich 动态面板实时渲染路口状态，按 Ctrl+C 停止。
2. **Web 模式** — 启动本地 Gradio 服务，浏览器打开可视化操作面板。
3. **后端验证模式** — 静默运行并输出断言结果。

也可通过命令行参数直接指定模式：

```
python run.py --mode console --duration 30 --refresh 0.3
python run.py --mode validate --seconds 30
python run.py --mode web --port 7860
```

### 命令行参数一览

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--mode` | `menu` / `console` / `validate` / `web` | `menu` |
| `--validate` | 等同于 `--mode validate` | — |
| `--seconds` | 验证模式运行时长（秒） | `20` |
| `--print-every` | 验证模式输出间隔（秒） | `2` |
| `--duration` | 控制台模式运行时长（秒），`0` 表示持续 | `0` |
| `--refresh` | 控制台模式刷新间隔（秒） | `0.5` |
| `--host` | Web 模式绑定地址 | `127.0.0.1` |
| `--port` | Web 模式端口 | `7860` |
| `--share` | Web 模式启用 Gradio 外网分享 | 关闭 |
| `--no-start-prompt` | 跳过启动确认提示 | — |

## 📁 核心文件

| 文件 | 说明 |
|---|---|
| `core.py` | 后端核心：信号灯守护线程、车辆生成引擎、调度循环、快照统计、违规检测 |
| `console.py` | 控制台 UI：Rich Live 动态面板、路口 ASCII 示意图、事件流渲染 |
| `web.py` | Web 前端：Gradio Blocks 界面、参数调节、定时刷新、控制器封装 |
| `run.py` | 统一入口：argparse 参数解析、交互式菜单、模式分发 |
| `build_exe.bat` | PyInstaller 打包脚本（单文件 exe，仅控制台 + 验证模式） |
| `requirements.txt` | 依赖声明（Rich + PyInstaller 为必选，Gradio 为可选） |

## 📦 打包为 EXE

运行 `build_exe.bat` 将项目打包为单个 `traffic_sim.exe`。

> **注意**：因 PyInstaller 与 Gradio 静态资源兼容性问题，打包后**禁用 Web 模式**，仅支持控制台和验证模式。Web 调试请直接用源码运行 `python run.py --mode web`。
