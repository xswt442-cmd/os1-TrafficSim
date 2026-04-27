from __future__ import annotations

import time
from typing import Dict, Optional

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

# 控制台模式相关的函数，供调用
def ask_console_start() -> bool:
    print("\n[控制台模式准备就绪]")
    print("- 将每隔一段时间刷新显示路口状态")
    print("- 按 Ctrl+C 可随时停止")
    ans = input("按回车开始，输入 q 取消: ").strip().lower()
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
        print("已取消进入控制台模式。")
        return

    backend = TrafficSimulationBackend()
    backend.start()
    start = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            if runtime_sec is not None and now - start >= runtime_sec:
                break

            snap = backend.snapshot()
            print("\033[2J\033[H", end="")
            print(render_console(snap))
            time.sleep(refresh_interval_sec)
    except KeyboardInterrupt:
        print("\n检测到手动中断，正在停止仿真...")
    finally:
        backend.stop()

    print("控制台模式已结束。")
