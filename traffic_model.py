from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from mesa import Agent, Model


Point = Tuple[float, float]


@dataclass(frozen=True)
class VehicleSpec:
    length: float
    width: float
    max_speed: float
    acceleration: float
    color: str


VEHICLE_SPECS: Dict[str, VehicleSpec] = {
    "car": VehicleSpec(length=32, width=18, max_speed=5.0, acceleration=0.7, color="#2563eb"),
    "motor": VehicleSpec(length=20, width=10, max_speed=6.4, acceleration=0.9, color="#f59e0b"),
}


PATHS: Dict[str, List[Point]] = {
    "through": [(940, 238), (-60, 238)],
    "entry": [(940, 238), (390, 238), (330, 278), (330, 660)],
    "exit": [(710, 660), (610, 512), (510, 355), (430, 238), (-60, 238)],
}


CONFLICT_CENTER: Point = (395, 244)
CONFLICT_RADIUS = 58
SLOW_LANE_Y = 238
SLOW_LANE_TOLERANCE = 42


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def interpolate(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def path_lengths(path: List[Point]) -> List[float]:
    lengths = [0.0]
    total = 0.0
    for i in range(1, len(path)):
        total += distance(path[i - 1], path[i])
        lengths.append(total)
    return lengths


def point_at(path: List[Point], lengths: List[float], s: float) -> Point:
    if s <= 0:
        return path[0]
    if s >= lengths[-1]:
        return path[-1]
    for i in range(1, len(lengths)):
        if s <= lengths[i]:
            segment_length = lengths[i] - lengths[i - 1]
            t = (s - lengths[i - 1]) / segment_length if segment_length else 0
            return interpolate(path[i - 1], path[i], t)
    return path[-1]


def angle_at(path: List[Point], lengths: List[float], s: float) -> float:
    look_back = point_at(path, lengths, max(0, s - 4))
    look_ahead = point_at(path, lengths, min(lengths[-1], s + 4))
    return math.atan2(look_ahead[1] - look_back[1], look_ahead[0] - look_back[0])


def slow_lane_progress(position: Point) -> Optional[float]:
    x, y = position
    if -60 <= x <= 940 and abs(y - SLOW_LANE_Y) <= SLOW_LANE_TOLERANCE:
        return 940 - x
    return None


class VehicleAgent(Agent):
    def __init__(
        self,
        model: "MallTrafficModel",
        vehicle_type: str,
        route: str,
        patience: float,
    ) -> None:
        super().__init__(model)
        self.vehicle_type = vehicle_type
        self.route = route
        self.path = PATHS[route]
        self.lengths = path_lengths(self.path)
        self.path_position = 0.0
        self.speed = 0.0
        self.patience = max(1.0, patience)
        self.wait_time = 0
        self.completed = False
        self.near_collision = False
        self.spec = VEHICLE_SPECS[vehicle_type]
        self.position = point_at(self.path, self.lengths, self.path_position)
        self.angle = angle_at(self.path, self.lengths, self.path_position)

    @property
    def remaining(self) -> float:
        return self.lengths[-1] - self.path_position

    @property
    def in_conflict_zone(self) -> bool:
        return distance(self.position, CONFLICT_CENTER) <= CONFLICT_RADIUS

    @property
    def approaching_conflict(self) -> bool:
        return distance(self.position, CONFLICT_CENTER) <= CONFLICT_RADIUS * 2.1

    def _gap_to_leader(self, agents: List["VehicleAgent"]) -> Optional[float]:
        leaders = []
        own_lane_progress = slow_lane_progress(self.position)

        for other in agents:
            if other is self:
                continue

            if other.route == self.route and other.path_position > self.path_position:
                if self.vehicle_type == "motor" and other.vehicle_type == "motor":
                    leaders.append(other.path_position - self.path_position - other.spec.length * 0.45)
                elif self.vehicle_type == "motor":
                    leaders.append(other.path_position - self.path_position - other.spec.length * 0.55)
                else:
                    leaders.append(other.path_position - self.path_position - other.spec.length)
                continue

            other_lane_progress = slow_lane_progress(other.position)
            if own_lane_progress is None or other_lane_progress is None:
                continue

            if other_lane_progress > own_lane_progress:
                if self.vehicle_type == "motor":
                    side_gap_factor = 0.35 if other.vehicle_type == "motor" else 0.48
                    leaders.append(other_lane_progress - own_lane_progress - other.spec.length * side_gap_factor)
                else:
                    leaders.append(other_lane_progress - own_lane_progress - other.spec.length)

        return min(leaders) if leaders else None

    def _conflict_blocked(self, agents: List["VehicleAgent"]) -> bool:
        if not self.approaching_conflict:
            return False

        blockers = [
            other
            for other in agents
            if other is not self and other.route != self.route and other.in_conflict_zone
        ]
        if self.route == "exit":
            blockers.extend(
                other
                for other in agents
                if other is not self
                and slow_lane_progress(other.position) is not None
                and 500 <= slow_lane_progress(other.position) <= 620
            )
        elif self.route == "through":
            blockers.extend(
                other
                for other in agents
                if other is not self and other.route in {"entry", "exit"} and other.in_conflict_zone
            )

        if not blockers:
            return False

        if self.vehicle_type == "motor":
            car_blockers = sum(1 for other in blockers if other.vehicle_type == "car")
            motor_blockers = len(blockers) - car_blockers
            can_filter = car_blockers < 2 and motor_blockers < 4
            if can_filter and self.wait_time <= self.patience * 1.8:
                return False

        forced_entry = self.wait_time > self.patience * 1.35
        if forced_entry:
            self.near_collision = True
            self.model.near_collisions += 1
            return False
        return True

    def step(self) -> None:
        agents = self.model.vehicles
        gap = self._gap_to_leader(agents)
        min_gap = self.spec.length * (0.38 if self.vehicle_type == "motor" else 1.15)
        braking_horizon = self.speed * (0.85 if self.vehicle_type == "motor" else 1.8)
        blocked_by_leader = gap is not None and gap < min_gap + braking_horizon
        blocked_by_conflict = self._conflict_blocked(agents)

        if blocked_by_leader or blocked_by_conflict:
            deceleration = 0.55 if self.vehicle_type == "motor" and blocked_by_leader else 1.2
            self.speed = max(0.0, self.speed - deceleration)
            self.wait_time += 1
            self.model.total_wait += 0.35 if self.vehicle_type == "motor" else 1
        else:
            patience_factor = 1.08 if self.wait_time > self.patience else 1.0
            clear_distance = 44 if self.vehicle_type == "motor" else 92
            clear_headway = gap is None or gap > max(clear_distance, self.spec.length * 3.4)
            if clear_headway:
                recovery_speed = self.spec.max_speed * (0.9 if self.vehicle_type == "motor" else 0.82)
                if not self.wait_time:
                    recovery_speed = self.spec.max_speed * 0.92
                self.speed = max(self.speed + self.spec.acceleration, recovery_speed)
            else:
                self.speed = self.speed + self.spec.acceleration
            self.speed = min(self.spec.max_speed * patience_factor, self.speed)
            self.wait_time = max(0, self.wait_time - 1)

        self.path_position += self.speed
        self.position = point_at(self.path, self.lengths, self.path_position)
        self.angle = angle_at(self.path, self.lengths, self.path_position)
        self.completed = self.path_position >= self.lengths[-1]


class MallTrafficModel(Model):
    def __init__(
        self,
        car_volume: float = 28,
        motor_volume: float = 42,
        entry_flow: float = 35,
        exit_flow: float = 30,
        patience: float = 18,
        seed: Optional[int] = None,
    ) -> None:
        try:
            super().__init__(rng=seed)
        except TypeError:
            super().__init__(seed=seed)
        self.random = random.Random(seed)
        self.tick = 0
        self.car_volume = car_volume
        self.motor_volume = motor_volume
        self.entry_flow = entry_flow
        self.exit_flow = exit_flow
        self.patience = patience
        self.vehicles: List[VehicleAgent] = []
        self.completed = 0
        self.total_wait = 0
        self.near_collisions = 0
        self.spawn_blocked = 0

    def _spawn_probability(self, vehicles_per_minute: float) -> float:
        return max(0.0, min(0.95, vehicles_per_minute / 60.0 / 2.0))

    def _vehicle_type(self, route: str) -> str:
        if route == "exit":
            return "car"

        car_prob = self.car_volume / max(1.0, self.car_volume + self.motor_volume)
        return "car" if self.random.random() < car_prob else "motor"

    def _route_for_main_lane(self) -> str:
        total = max(1.0, self.entry_flow + 40.0)
        return "entry" if self.random.random() < self.entry_flow / total else "through"

    def _spawn(self, route: str) -> None:
        vehicle_type = self._vehicle_type(route)
        spawn = PATHS[route][0]
        occupied = False
        for other in self.vehicles:
            if vehicle_type == "motor":
                min_spawn_gap = 16 if other.vehicle_type == "motor" else 24
            else:
                min_spawn_gap = 24 if other.vehicle_type == "motor" else 44

            same_spot_blocked = distance(other.position, spawn) < min_spawn_gap
            same_lane_blocked = (
                slow_lane_progress(spawn) is not None
                and slow_lane_progress(other.position) is not None
                and abs(slow_lane_progress(other.position) - slow_lane_progress(spawn)) < min_spawn_gap
            )
            if same_spot_blocked or same_lane_blocked:
                occupied = True
                break
        if occupied:
            self.spawn_blocked += 1
            return

        individual_patience = self.random.gauss(self.patience, self.patience * 0.28)
        agent = VehicleAgent(self, vehicle_type, route, individual_patience)
        self.vehicles.append(agent)

    def step(self) -> None:
        self.tick += 1
        main_volume = self.car_volume + self.motor_volume
        if self.random.random() < self._spawn_probability(main_volume):
            self._spawn(self._route_for_main_lane())
        if self.random.random() < self._spawn_probability(self.exit_flow):
            self._spawn("exit")

        for agent in sorted(self.vehicles, key=lambda item: item.path_position, reverse=True):
            agent.step()

        survivors = []
        for agent in self.vehicles:
            if agent.completed:
                self.completed += 1
            else:
                survivors.append(agent)
        self.vehicles = survivors

    def snapshot(self) -> Dict[str, object]:
        active_waiting = sum(1 for agent in self.vehicles if agent.speed < 0.35)
        car_waiting = sum(1 for agent in self.vehicles if agent.vehicle_type == "car" and agent.speed < 0.35)
        motor_waiting = sum(1 for agent in self.vehicles if agent.vehicle_type == "motor" and agent.speed < 0.35)
        avg_speed = sum(agent.speed for agent in self.vehicles) / max(1, len(self.vehicles))
        congestion = min(100, round((car_waiting * 9 + motor_waiting * 2.5 + self.spawn_blocked * 0.25 + self.total_wait * 0.025), 1))
        return {
            "tick": self.tick,
            "vehicles": [
                {
                    "id": agent.unique_id,
                    "type": agent.vehicle_type,
                    "route": agent.route,
                    "x": round(agent.position[0], 1),
                    "y": round(agent.position[1], 1),
                    "angle": agent.angle,
                    "speed": round(agent.speed, 2),
                    "waitTime": round(agent.wait_time / 10, 1),
                    "waiting": agent.speed < 0.35,
                    "nearCollision": agent.near_collision,
                    "length": agent.spec.length,
                    "width": agent.spec.width,
                    "color": agent.spec.color,
                }
                for agent in self.vehicles
            ],
            "metrics": {
                "active": len(self.vehicles),
                "completed": self.completed,
                "waiting": active_waiting,
                "carWaiting": car_waiting,
                "motorWaiting": motor_waiting,
                "avgSpeed": round(avg_speed, 2),
                "totalWait": self.total_wait,
                "nearCollisions": self.near_collisions,
                "spawnBlocked": self.spawn_blocked,
                "congestion": congestion,
            },
        }
