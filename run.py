from __future__ import annotations

import argparse

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from console import run_console_mode
from core import validate_backend

try:
    from web import run_web_mode
    _WEB_AVAILABLE = True
except ImportError:
    _WEB_AVAILABLE = False

_console = Console()

# 准备渲染函数
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="十字路口交通仿真统一入口")
    parser.add_argument(
        "--mode",
        choices=["menu", "console", "validate", "web"],
        default="menu",
        help="运行模式：menu 菜单选择，console 控制台，validate 后端验证，web 网页界面",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="兼容参数：等同于 --mode validate",
    )

    parser.add_argument(
        "--seconds",
        type=int,
        default=20,
        help="验证模式运行时长（秒）",
    )
    parser.add_argument(
        "--print-every",
        type=int,
        default=2,
        help="验证模式输出间隔（秒）",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="控制台模式运行时长（秒），0 表示持续运行直到 Ctrl+C",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=0.5,
        help="控制台模式刷新间隔（秒）",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Web 模式绑定地址",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Web 模式端口",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Web 模式启用 Gradio 外网分享",
    )
    parser.add_argument(
        "--no-start-prompt",
        action="store_true",
        help="跳过开始前确认提示（便于自动化测试）",
    )
    return parser


def prompt_web_start(host: str, port: int) -> bool:
    _console.print()
    _console.print("[bold cyan]Web 模式准备就绪[/]")
    _console.print(f"  - 即将启动地址: [bold underline]http://{host}:{port}[/]")
    _console.print("  - 启动后可在浏览器点击 [bold]启动仿真[/] 按钮")
    ans = _console.input("[bold]按回车启动，输入 q 取消:[/] ").strip().lower()
    return ans != "q"

# 选择模式
def choose_mode_interactively() -> str:
    menu = Text()
    menu.append("\n══════════ 十字路口交通仿真 ══════════\n", style="bold cyan")
    menu.append("  1) ", style="bold")
    menu.append("控制台模式\n")
    if _WEB_AVAILABLE:
        menu.append("  2) ", style="bold")
        menu.append("Web 模式\n")
    else:
        menu.append("  2) ", style="bold dim")
        menu.append("Web 模式 [dim](不可用 - 请通过源码运行)[/]\n")
    menu.append("  3) ", style="bold")
    menu.append("后端验证模式\n")
    menu.append("  q) ", style="bold")
    menu.append("退出\n")
    _console.print(Panel(menu, border_style="cyan"))

    while True:
        choice = _console.input("[bold]请选择模式 [1/2/3/q]:[/] ").strip().lower()
        if choice == "1":
            return "console"
        if choice == "2":
            if not _WEB_AVAILABLE:
                _console.print("[yellow]Web 模式不可用：gradio 未安装。请通过源码 python run.py --mode web 运行。[/]")
                continue
            return "web"
        if choice == "3":
            return "validate"
        if choice == "q":
            return "quit"
        _console.print("[red]输入无效，请重试。[/]")

# 主控
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    mode = "validate" if args.validate else args.mode
    if mode == "menu":
        mode = choose_mode_interactively()
        if mode == "quit":
            _console.print("[dim]已退出。[/]")
            return

    if mode == "web":
        if not _WEB_AVAILABLE:
            _console.print("[yellow]Web 模式不可用：gradio 未安装。请通过源码 python run.py --mode web 运行。[/]")
            return
        if not args.no_start_prompt and not prompt_web_start(args.host, args.port):
            _console.print("[yellow]已取消进入 Web 模式。[/]")
            return
        run_web_mode(host=args.host, port=args.port, share=args.share)
        return

    if mode == "validate":
        validate_backend(runtime_sec=args.seconds, print_every_sec=args.print_every)
        return

    if mode == "console":
        runtime_sec = None if args.duration <= 0 else args.duration
        run_console_mode(
            runtime_sec=runtime_sec,
            refresh_interval_sec=args.refresh,
            start_prompt=not args.no_start_prompt,
        )
        return


if __name__ == "__main__":
    main()
