from __future__ import annotations

import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, Dict, List, Optional, Tuple

# 方向
class Direction(str, Enum):
    EAST = "E"
    WEST = "W"
    SOUTH = "S"
    NORTH = "N"

# 红绿灯相位
class Phase(str, Enum):
    EW_GREEN = "EW_GREEN"
    NS_GREEN = "NS_GREEN"

# 车
class VehicleType(str, Enum):
    NORMAL = "normal"
    FIRE_TRUCK = "fire_truck"
    AMBULANCE = "ambulance"
    POLICE = "police"

    @property
    def is_emergency(self) -> bool:
        return self in {VehicleType.FIRE_TRUCK, VehicleType.AMBULANCE, VehicleType.POLICE}

# 车辆数据类
@dataclass(frozen=True)
class Vehicle:
    vehicle_id: int
    direction: Direction
    lane: int
    vehicle_type: VehicleType
    created_at: float

# 底层后端核心
class TrafficSimulationBackend:
    """十字路口交通仿真后端核心。"""

    # 面向路口中心时的右侧受控车道: W2 / E1 / N1 / S2
    CONTROLLED_LANE_BY_DIRECTION: Dict[Direction, int] = {
        Direction.WEST: 2,
        Direction.EAST: 1,
        Direction.NORTH: 1,
        Direction.SOUTH: 2,
    }

    def __init__(
        self,
        green_duration_sec: int = 8,
        generate_interval_sec: float = 0.35,
        emergency_ratio: float = 0.08,
        crossing_time_sec: float = 0.18,
        rng_seed: Optional[int] = None,
    ) -> None:
        if green_duration_sec <= 0:
            raise ValueError("green_duration_sec 必须大于 0")
        if generate_interval_sec <= 0:
            raise ValueError("generate_interval_sec 必须大于 0")
        if crossing_time_sec <= 0:
            raise ValueError("crossing_time_sec 必须大于 0")
        if not 0.0 <= emergency_ratio <= 1.0:
            raise ValueError("emergency_ratio 必须在 [0, 1] 范围内")

        self.green_duration_sec = green_duration_sec
        self.generate_interval_sec = generate_interval_sec
        self.emergency_ratio = emergency_ratio
        self.crossing_time_sec = crossing_time_sec
        self.random = random.Random(rng_seed)

        self._lock = threading.RLock()
        self._phase_cond = threading.Condition(self._lock)
        self._intersection_sem = threading.Semaphore(1)
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []

        self._phase: Phase = Phase.EW_GREEN
        self._phase_started_at: float = time.monotonic()
        self._phase_remaining_sec: int = self.green_duration_sec

        self._vehicle_id_seq = 0
        # 每个方向有两条车道，但仅“面向路口中心的右侧进路车道”受信号灯控制并计数。
        self._lanes: Dict[Tuple[Direction, int], Deque[Vehicle]] = {
            (direction, lane): deque()
            for direction, lane in self.CONTROLLED_LANE_BY_DIRECTION.items()
        }
        self._lane_round_robin = list(self._lanes.keys())
        self._lane_cursor = 0

        self._started_at = time.monotonic()
        self._generated_total = 0
        self._passed_total = 0
        self._passed_by_direction: Dict[Direction, int] = {d: 0 for d in Direction}
        self._passed_emergency = 0
        self._waiting_time_sum = 0.0
        self._max_waiting_time = 0.0
        self._ordinary_red_light_violation = 0
        self._fifo_violations = 0
        self._last_passed_id_by_lane: Dict[Tuple[Direction, int], int] = {
            lane_key: -1 for lane_key in self._lanes
        }
        self._event_log: Deque[str] = deque(maxlen=200)

    def start(self) -> None:
        with self._lock:
            if self._threads:
                return
            self._stop_event.clear()
            self._started_at = time.monotonic()
            self._phase_started_at = self._started_at
            self._phase_remaining_sec = self.green_duration_sec

            self._threads = [
                threading.Thread(target=self._traffic_light_loop, name="traffic-light", daemon=True),
                threading.Thread(target=self._vehicle_generator_loop, name="vehicle-generator", daemon=True),
                threading.Thread(target=self._scheduler_loop, name="scheduler", daemon=True),
            ]
            for thread in self._threads:
                thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._phase_cond:
            self._phase_cond.notify_all()
        for thread in self._threads:
            thread.join(timeout=1.0)
        self._threads.clear()

    def is_running(self) -> bool:
        return bool(self._threads) and not self._stop_event.is_set()
    # 快照
    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            lane_queue_sizes = {
                f"{direction.value}{lane}": 0 for direction in Direction for lane in (1, 2)
            }
            for (direction, lane), queue in self._lanes.items():
                lane_queue_sizes[f"{direction.value}{lane}"] = len(queue)
            elapsed = time.monotonic() - self._started_at
            avg_wait = self._waiting_time_sum / self._passed_total if self._passed_total else 0.0
            return {
                "elapsed_sec": round(elapsed, 2),
                "phase": self._phase.value,
                "phase_remaining_sec": self._phase_remaining_sec,
                "generated_total": self._generated_total,
                "passed_total": self._passed_total,
                "passed_by_direction": {
                    direction.value: count for direction, count in self._passed_by_direction.items()
                },
                "passed_emergency": self._passed_emergency,
                "avg_wait_sec": round(avg_wait, 3),
                "max_wait_sec": round(self._max_waiting_time, 3),
                "ordinary_red_light_violation": self._ordinary_red_light_violation,
                "fifo_violations": self._fifo_violations,
                "lane_queue_sizes": lane_queue_sizes,
                "recent_events": list(self._event_log)[-12:],
            }
    # 信号灯循环
    def _traffic_light_loop(self) -> None:
        last_second_mark = time.monotonic()
        while not self._stop_event.is_set():
            now = time.monotonic()
            if now - last_second_mark >= 1.0:
                with self._phase_cond:
                    elapsed = int(now - self._phase_started_at)
                    remain = self.green_duration_sec - elapsed
                    if remain <= 0:
                        self._phase = (
                            Phase.NS_GREEN if self._phase == Phase.EW_GREEN else Phase.EW_GREEN
                        )
                        self._phase_started_at = now
                        self._phase_remaining_sec = self.green_duration_sec
                        self._event_log.append(
                            f"信号灯切换 -> {self._phase.value} (t={int(now - self._started_at)}s)"
                        )
                        self._phase_cond.notify_all()
                    else:
                        self._phase_remaining_sec = remain
                last_second_mark = now
            time.sleep(0.05)
    # 车辆生成循环
    def _vehicle_generator_loop(self) -> None:
        while not self._stop_event.is_set():
            direction = self.random.choice(list(Direction))
            lane = self.CONTROLLED_LANE_BY_DIRECTION[direction]
            vehicle_type = self._pick_vehicle_type()

            with self._lock:
                self._vehicle_id_seq += 1
                vehicle = Vehicle(
                    vehicle_id=self._vehicle_id_seq,
                    direction=direction,
                    lane=lane,
                    vehicle_type=vehicle_type,
                    created_at=time.monotonic(),
                )
                self._lanes[(direction, lane)].append(vehicle)
                self._generated_total += 1

            time.sleep(self.generate_interval_sec)
    # 调度循环
    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            lane_keys = self._next_lane_scan_order()
            selected: Optional[Tuple[Tuple[Direction, int], Vehicle]] = None

            with self._lock:
                for lane_key in lane_keys:
                    queue = self._lanes[lane_key]
                    if not queue:
                        continue
                    candidate = queue[0]
                    if self._can_pass(candidate):
                        selected = (lane_key, candidate)
                        break

            if selected is None:
                time.sleep(0.02)
                continue

            lane_key, vehicle = selected
            if not self._intersection_sem.acquire(timeout=0.05):
                continue
            try:
                with self._lock:
                    queue = self._lanes[lane_key]
                    if not queue or queue[0].vehicle_id != vehicle.vehicle_id:
                        continue
                    passed = queue.popleft()
                    self._register_passed_vehicle(lane_key, passed)
                time.sleep(self.crossing_time_sec)
            finally:
                self._intersection_sem.release()
    # 获得新的车道扫描顺序
    def _next_lane_scan_order(self) -> List[Tuple[Direction, int]]:
        with self._lock:
            start = self._lane_cursor
            self._lane_cursor = (self._lane_cursor + 1) % len(self._lane_round_robin)
            return self._lane_round_robin[start:] + self._lane_round_robin[:start]
    # 是否可以通行
    def _can_pass(self, vehicle: Vehicle) -> bool:
        if vehicle.vehicle_type.is_emergency:
            return True
        if self._phase == Phase.EW_GREEN:
            return vehicle.direction in {Direction.EAST, Direction.WEST}
        return vehicle.direction in {Direction.SOUTH, Direction.NORTH}
    # 注册通行车辆并记录事件
    def _register_passed_vehicle(self, lane_key: Tuple[Direction, int], vehicle: Vehicle) -> None:
        now = time.monotonic()
        wait = now - vehicle.created_at

        self._passed_total += 1
        self._passed_by_direction[vehicle.direction] += 1
        self._waiting_time_sum += wait
        self._max_waiting_time = max(self._max_waiting_time, wait)

        if vehicle.vehicle_type.is_emergency:
            self._passed_emergency += 1

        if (
            not vehicle.vehicle_type.is_emergency
            and self._phase == Phase.EW_GREEN
            and vehicle.direction in {Direction.SOUTH, Direction.NORTH}
        ):
            self._ordinary_red_light_violation += 1
        if (
            not vehicle.vehicle_type.is_emergency
            and self._phase == Phase.NS_GREEN
            and vehicle.direction in {Direction.EAST, Direction.WEST}
        ):
            self._ordinary_red_light_violation += 1

        last_id = self._last_passed_id_by_lane[lane_key]
        if vehicle.vehicle_id < last_id:
            self._fifo_violations += 1
        self._last_passed_id_by_lane[lane_key] = vehicle.vehicle_id

        ev_type = "紧急" if vehicle.vehicle_type.is_emergency else "普通"
        self._event_log.append(
            f"通行 #{vehicle.vehicle_id:04d} {ev_type} {vehicle.direction.value}{vehicle.lane} 等待={wait:.2f}s"
        )

    def _pick_vehicle_type(self) -> VehicleType:
        if self.random.random() >= self.emergency_ratio:
            return VehicleType.NORMAL
        return self.random.choice(
            [VehicleType.FIRE_TRUCK, VehicleType.AMBULANCE, VehicleType.POLICE]
        )

# 后端验证
def validate_backend(runtime_sec: int = 20, print_every_sec: int = 2) -> Dict[str, object]:
    backend = TrafficSimulationBackend()
    backend.start()
    begin = time.monotonic()
    next_print = begin

    try:
        while True:
            now = time.monotonic()
            if now - begin >= runtime_sec:
                break
            if now >= next_print:
                snap = backend.snapshot()
                print(
                    "[t={elapsed:>5.1f}s] 相位={phase:<8} 剩余={remain:>2}s "
                    "生成={gen:>4} 通行={pas:>4} 紧急={emg:>3} 平均等待={avg:.2f}s".format(
                        elapsed=snap["elapsed_sec"],
                        phase=snap["phase"],
                        remain=snap["phase_remaining_sec"],
                        gen=snap["generated_total"],
                        pas=snap["passed_total"],
                        emg=snap["passed_emergency"],
                        avg=snap["avg_wait_sec"],
                    )
                )
                next_print += print_every_sec
            time.sleep(0.05)
    finally:
        backend.stop()

    result = backend.snapshot()
    assert result["generated_total"] > 0, "没有生成车辆，仿真失败"
    assert result["passed_total"] > 0, "没有车辆通行，调度失败"
    assert result["ordinary_red_light_violation"] == 0, "普通车辆出现闯红灯通行"
    assert result["fifo_violations"] == 0, "至少一条车道出现 FIFO 顺序违规"

    print("\n后端验证通过。")
    print(
        "最终统计: 生成={gen}, 通行={pas}, 紧急={emg}, 平均等待={avg}s, 最大等待={mx}s".format(
            gen=result["generated_total"],
            pas=result["passed_total"],
            emg=result["passed_emergency"],
            avg=result["avg_wait_sec"],
            mx=result["max_wait_sec"],
        )
    )
    return result
