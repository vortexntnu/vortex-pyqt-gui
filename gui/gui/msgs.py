from dataclasses import dataclass

@dataclass
class WaypointMessage:
    mode: int
    convergence_cm: float
    position: dict
    rpy: dict
