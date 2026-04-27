from __future__ import annotations

import argparse

from console import run_console_mode
from core import validate_backend
from web import run_web_mode

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
    print("\n[Web 模式准备就绪]")
    print(f"- 即将启动地址: http://{host}:{port}")
    print("- 启动后可在浏览器点击“启动仿真”按钮")
    ans = input("按回车启动，输入 q 取消: ").strip().lower()
    return ans != "q"

# 选择模式
def choose_mode_interactively() -> str:
    print("\n================ 十字路口交通仿真 ================")
    print("1) 控制台模式")
    print("2) Web 模式（受 pyinstaller 打包影响，exe无法展示，直接运行run脚本即可")
    print("3) 后端验证模式")
    print("q) 退出")
    while True:
        choice = input("请选择模式 [1/2/3/q]: ").strip().lower()
        if choice == "1":
            return "console"
        if choice == "2":
            return "web"
        if choice == "3":
            return "validate"
        if choice == "q":
            return "quit"
        print("输入无效，请重试。")

# 主控
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    mode = "validate" if args.validate else args.mode
    if mode == "menu":
        mode = choose_mode_interactively()
        if mode == "quit":
            print("已退出。")
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

    if not args.no_start_prompt and not prompt_web_start(args.host, args.port):
        print("已取消进入 Web 模式。")
        return

    run_web_mode(host=args.host, port=args.port, share=args.share)


if __name__ == "__main__":
    main()
