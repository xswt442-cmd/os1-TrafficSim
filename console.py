from __future__ import annotations

import time
from typing import Dict, Optional

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from core import Phase, TrafficSimulationBackend

# 显示的“图形”界面
def _phase_to_cn(phase: str) -> str:
    if phase == Phase.EW_GREEN.value:
        return "东西向绿灯"
    if phase == Phase.NS_GREEN.value:
        return "南北向绿灯"
    return phase

# 灯状态文本
def _light_text(is_green: bool) -> str:
    return "GREEN" if is_green else "RED"

# 车道视图
def _lane_view(count: int, width: int = 8) -> str:
    fill = min(count, width)
    suffix = "+" if count > width else ""
    return f"🚗C{count:02d}[" + "#" * fill + "." * (width - fill) + suffix + "]"

# 反向车道视图
def _reverse_lane_view() -> str:
    return "↔REV[........]"

# 渲染函数，供调用
def render_console(snap: Dict[str, object]) -> str:
    lane = snap["lane_queue_sizes"]
    passed = snap["passed_by_direction"]
    recent_events = snap["recent_events"][-6:]
    phase = str(snap["phase"])
    phase_cn = _phase_to_cn(phase)
    ew_green = phase == Phase.EW_GREEN.value
    ns_green = phase == Phase.NS_GREEN.value
    ew_emoji = "🟢" if ew_green else "🔴"
    ns_emoji = "🟢" if ns_green else "🔴"

    w1 = int(lane["W1"])
    w2 = int(lane["W2"])
    e1 = int(lane["E1"])
    e2 = int(lane["E2"])
    n1 = int(lane["N1"])
    n2 = int(lane["N2"])
    s1 = int(lane["S1"])
    s2 = int(lane["S2"])

    left_field = 30
    road = "-----++-----"
    right_field = 30
    total_width = left_field + len(road) + right_field
    center_col = left_field + road.index("++")

    # 受控右车道: W2 / E1 / N1 / S2
    w1_view = _reverse_lane_view()
    w2_view = _lane_view(w2)
    e1_view = _lane_view(e1)
    e2_view = _reverse_lane_view()
    n1_view = _lane_view(n1)
    n2_view = _reverse_lane_view()
    s1_view = _reverse_lane_view()
    s2_view = _lane_view(s2)

    def vline() -> str:
        return " " * center_col + "||"

    def ns_line(left_label: str, right_label: str) -> str:
        left = left_label.rjust(center_col)
        right = right_label.ljust(total_width - (center_col + 2))
        return left + "||" + right

    north_line = ns_line(f"N1 {n1_view}", f"N2 {n2_view}")[1:]
    south_line = ns_line(f"S1 {s1_view}", f"S2 {s2_view}")

    lines = [
        "=" * total_width,
        "十字路口交通仿真 - 控制台模式",
        "=" * total_width,
        "运行时间: {t:>6.1f}s | 相位: {phase} | 相位剩余: {remain:>2}s".format(
            t=float(snap["elapsed_sec"]),
            phase=phase_cn,
            remain=int(snap["phase_remaining_sec"]),
        ),
        "信号灯状态: EW={ew} {ew_emoji}  NS={ns} {ns_emoji}  |  图例: 🚗计数车道, ↔REV反向不计".format(
            ew=_light_text(ew_green),
            ns=_light_text(ns_green),
            ew_emoji=ew_emoji,
            ns_emoji=ns_emoji,
        ),
        "生成: {gen:>5} | 通行: {pas:>5} | 紧急通行: {emg:>5} | 平均等待: {avg:.2f}s | 最大等待: {mx:.2f}s".format(
            gen=int(snap["generated_total"]),
            pas=int(snap["passed_total"]),
            emg=int(snap["passed_emergency"]),
            avg=float(snap["avg_wait_sec"]),
            mx=float(snap["max_wait_sec"]),
        ),
        "说明: 仅 W2/E1/N1/S2 为受控右车道（面向路口中心时的右侧）",
        "违规统计: 普通车闯红灯={rv} | FIFO顺序违规={fv}".format(
            rv=int(snap["ordinary_red_light_violation"]),
            fv=int(snap["fifo_violations"]),
        ),
        "-" * total_width,
        "路口示意图（两车道）",
        north_line,
        vline(),
        "W1 {w:<{lw}} {road}E1 {e:<{rw}}".format(
            w=w1_view,
            lw=left_field - 4,
            road=road,
            e=e1_view,
            rw=right_field - 4,
        ),
        "W2 {w:<{lw}}{road}E2 {e:<{rw}}".format(
            w=w2_view,
            lw=left_field - 4,
            road=road,
            e=e2_view,
            rw=right_field - 4,
        ),
        vline(),
        south_line,
        "-" * total_width,
        "方向通行统计: 东={e:>5} 西={w:>5} 南={s:>5} 北={n:>5}".format(
            e=int(passed["E"]),
            w=int(passed["W"]),
            s=int(passed["S"]),
            n=int(passed["N"]),
        ),
        "车道计数校验(反向应为0): W1={w1} E2={e2} N2={n2} S1={s1}".format(
            w1=w1,
            e2=e2,
            n2=n2,
            s1=s1,
        ),
        "-" * total_width,
        "最近事件:",
    ]

    if recent_events:
        lines.extend([f"  - {event}" for event in recent_events])
    else:
        lines.append("  - 暂无事件")

    lines.append("=" * total_width)
    lines.append("提示: 按 Ctrl+C 停止控制台模式")
    return "\n".join(lines)


def render_rich(snap: Dict[str, object]) -> Panel:
    """返回 rich Panel，用于控制台 live 模式渲染。"""
    phase = str(snap["phase"])
    phase_cn = _phase_to_cn(phase)
    ew_green = phase == Phase.EW_GREEN.value
    ns_green = phase == Phase.NS_GREEN.value

    stats = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    stats.add_column(style="bold cyan")
    stats.add_column(style="white")
    stats.add_row("运行时间", f"{float(snap['elapsed_sec']):.1f} s")
    stats.add_row("相位", f"{phase_cn}（剩余 {int(snap['phase_remaining_sec'])}s）")
    ew_label = "[bold green]GREEN[/]" if ew_green else "[bold red]RED[/]"
    ns_label = "[bold green]GREEN[/]" if ns_green else "[bold red]RED[/]"
    stats.add_row("信号灯", f"EW={ew_label}  NS={ns_label}")
    stats.add_row("")
    stats.add_row("生成车辆", str(int(snap["generated_total"])))
    stats.add_row("通行车辆", str(int(snap["passed_total"])))
    stats.add_row("紧急通行", str(int(snap["passed_emergency"])))
    stats.add_row("平均等待", f"{float(snap['avg_wait_sec']):.3f} s")
    stats.add_row("最大等待", f"{float(snap['max_wait_sec']):.3f} s")
    rv = int(snap["ordinary_red_light_violation"])
    fv = int(snap["fifo_violations"])
    rv_style = "[bold red]" if rv > 0 else "[green]"
    fv_style = "[bold red]" if fv > 0 else "[green]"
    stats.add_row("违规", f"闯红灯={rv_style}{rv}[/]  FIFO={fv_style}{fv}[/]")

    passed = snap["passed_by_direction"]
    dir_text = Text()
    dir_text.append("方向通行: ", style="bold")
    dir_text.append(f"东={int(passed['E'])}  ", style="cyan")
    dir_text.append(f"西={int(passed['W'])}  ", style="yellow")
    dir_text.append(f"南={int(passed['S'])}  ", style="magenta")
    dir_text.append(f"北={int(passed['N'])}", style="blue")

    events_text = Text()
    recent_events = snap["recent_events"][-6:]
    if recent_events:
        for ev in recent_events:
            events_text.append(f"  • {ev}\n", style="dim")
    else:
        events_text.append("  (暂无事件)", style="dim italic")

    inner = Group(
        stats,
        Text(""),
        dir_text,
        Text(""),
        Text("── 路口示意图 ──", style="bold underline"),
        Text(render_console(snap)),
        Text(""),
        Text("── 最近事件 ──", style="bold underline"),
        events_text,
    )

    elapsed = float(snap["elapsed_sec"])
    title = f"[bold]🚦 十字路口交通仿真 - 控制台模式 [t={elapsed:.1f}s][/]"
    return Panel(inner, title=title, border_style="cyan", box=box.ROUNDED)

# 控制台模式相关的函数，供调用
def ask_console_start() -> bool:
    console = Console()
    console.print()
    console.print("[bold cyan]控制台模式准备就绪[/]")
    console.print("  • 将每隔一段时间刷新显示路口状态")
    console.print("  • 按 [bold]Ctrl+C[/] 可随时停止")
    ans = console.input("[bold]按回车开始，输入 q 取消:[/] ").strip().lower()
    return ans != "q"

# 控制台模式的运行函数，供调用
def run_console_mode(
    runtime_sec: Optional[int] = None,
    refresh_interval_sec: float = 0.5,
    start_prompt: bool = True,
) -> None:
    if refresh_interval_sec <= 0:
        raise ValueError("refresh_interval_sec 必须大于 0")

    if start_prompt and not ask_console_start():
        Console().print("[yellow]已取消进入控制台模式。[/]")
        return

    backend = TrafficSimulationBackend()
    backend.start()
    start = time.monotonic()
    rconsole = Console()

    try:
        snap = backend.snapshot()
        with Live(render_rich(snap), console=rconsole, refresh_per_second=4, screen=True) as live:
            while True:
                now = time.monotonic()
                if runtime_sec is not None and now - start >= runtime_sec:
                    break

                snap = backend.snapshot()
                live.update(render_rich(snap))
                time.sleep(refresh_interval_sec)
    except KeyboardInterrupt:
        rconsole.print("\n[bold yellow]检测到手动中断，正在停止仿真...[/]")
    finally:
        backend.stop()

    rconsole.print("[bold green]控制台模式已结束。[/]")
