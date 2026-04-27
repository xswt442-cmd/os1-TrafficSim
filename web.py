from __future__ import annotations

from typing import Optional, Tuple

from core import Phase, TrafficSimulationBackend
# 引入控制台模式的渲染函数
from console import render_console 

class WebSimulationController:
    def __init__(self) -> None:
        self.backend: Optional[TrafficSimulationBackend] = None

    def start(
        self,
        green_duration_sec: int,
        generate_interval_sec: float,
        emergency_ratio: float,
        crossing_time_sec: float,
    ) -> str:
        if self.backend is not None:
            self.backend.stop()

        self.backend = TrafficSimulationBackend(
            green_duration_sec=green_duration_sec,
            generate_interval_sec=generate_interval_sec,
            emergency_ratio=emergency_ratio,
            crossing_time_sec=crossing_time_sec,
        )
        self.backend.start()
        return "仿真已启动"

    def stop(self) -> str:
        if self.backend is None:
            return "仿真未启动"
        self.backend.stop()
        self.backend = None
        return "仿真已停止"

    # str 用于输出图形界面
    def snapshot(self) -> Tuple[str, str, str, str]:
        if self.backend is None:
            return "未运行", "请先点击启动仿真", "暂无事件", "```text\n等待运行...\n```"

        snap = self.backend.snapshot()
        phase = snap["phase"]
        if phase == Phase.EW_GREEN.value:
            phase_cn = "东西向绿灯"
        elif phase == Phase.NS_GREEN.value:
            phase_cn = "南北向绿灯"
        else:
            phase_cn = str(phase)

        status_md = (
            f"### 当前状态\n"
            f"- 运行时间: {snap['elapsed_sec']} s\n"
            f"- 相位: {phase_cn}\n"
            f"- 相位剩余: {snap['phase_remaining_sec']} s\n"
            f"- 生成车辆: {snap['generated_total']}\n"
            f"- 通行车辆: {snap['passed_total']}\n"
            f"- 紧急车辆通行: {snap['passed_emergency']}\n"
            f"- 平均等待: {snap['avg_wait_sec']} s\n"
            f"- 最大等待: {snap['max_wait_sec']} s\n"
            f"- 普通车闯红灯: {snap['ordinary_red_light_violation']}\n"
            f"- FIFO违规: {snap['fifo_violations']}"
        )

        lane = snap["lane_queue_sizes"]
        lane_md = (
            "### 车道排队\n"
            "- 说明: 仅面向路口中心时右侧车道 (W2/E1/N1/S2) 参与信号灯排队控制\n"
            "- 反向车道 (W1/E2/N2/S1) 不计排队，固定为 0\n"
            f"- 东向: E1={lane['E1']} E2={lane['E2']}\n"
            f"- 西向: W1={lane['W1']} W2={lane['W2']}\n"
            f"- 南向: S1={lane['S1']} S2={lane['S2']}\n"
            f"- 北向: N1={lane['N1']} N2={lane['N2']}"
        )

        events = snap["recent_events"]
        events_text = "\n".join(events) if events else "暂无事件"
        
        # 调用 console.py 中的函数生成图形，并用 Markdown 代码块包裹以保持等宽对齐
        console_view = render_console(snap)
        console_md = f"```text\n{console_view}\n```"

        return "运行中", status_md, lane_md + "\n\n### 最近事件\n" + events_text, console_md


def create_web_app():
    import gradio as gr

    controller = WebSimulationController()

    with gr.Blocks(title="十字路口交通仿真", theme=gr.themes.Soft()) as app:
        gr.Markdown("## 🚦 十字路口交通仿真系统")

        with gr.Row():
            green_duration_sec = gr.Slider(4, 20, value=8, step=1, label="绿灯时长（秒）")
            generate_interval_sec = gr.Slider(0.1, 1.5, value=0.35, step=0.05, label="车辆生成间隔（秒）")
            emergency_ratio = gr.Slider(0.0, 0.5, value=0.08, step=0.01, label="紧急车辆比例")
            crossing_time_sec = gr.Slider(0.05, 1.0, value=0.18, step=0.01, label="过路口耗时（秒）")

        with gr.Row():
            start_btn = gr.Button("▶️ 启动仿真", variant="primary")
            stop_btn = gr.Button("⏹️ 停止仿真", variant="stop")

        state_text = gr.Textbox(label="运行状态", value="未运行", interactive=False)
        
        # 左侧放数据统计，右侧放巨大的控制台图形
        with gr.Row():
            with gr.Column(scale=1):
                status_md = gr.Markdown("请先点击启动仿真")
                detail_md = gr.Markdown("暂无数据")
            with gr.Column(scale=2):
                gr.Markdown("### 实时路口监控视图")
                console_view_md = gr.Markdown("```text\n等待运行...\n```")

        start_btn.click(
            fn=controller.start,
            inputs=[green_duration_sec, generate_interval_sec, emergency_ratio, crossing_time_sec],
            outputs=[state_text],
        )
        stop_btn.click(fn=controller.stop, outputs=[state_text])

        # 定时器增加对 console_view_md 的更新
        timer = gr.Timer(0.5)
        timer.tick(
            fn=controller.snapshot, 
            outputs=[state_text, status_md, detail_md, console_view_md]
        )

    return app


def run_web_mode(host: str = "127.0.0.1", port: int = 7860, share: bool = False) -> None:
    app = create_web_app()
    app.launch(server_name=host, server_port=port, share=share)