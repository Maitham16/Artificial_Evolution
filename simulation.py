"""Drive consecutive generations without changing the fixed simulation step."""

from dataclasses import asdict
import math

from world import SIMULATION_STEP, World


SPEEDS = (1, 5, 20)


class EvolutionSimulation:
    def __init__(
        self, world: World, *, generation_limit: int | None = None,
        auto_advance: bool = True, speed: int = 1,
    ) -> None:
        if generation_limit is not None and (
            type(generation_limit) is not int or generation_limit < 1
        ):
            raise ValueError("Generation limit must be a positive integer.")
        if speed not in SPEEDS:
            raise ValueError(f"Speed must be one of {SPEEDS}.")
        self.world = world
        self.generation_limit = generation_limit
        self.auto_advance = auto_advance
        self.speed = speed
        self._accumulator = 0.0
        self._ticks = 0

    @property
    def finished(self) -> bool:
        return (
            self.generation_limit is not None
            and len(self.world.generation_history) >= self.generation_limit
        )

    @property
    def total_simulated_seconds(self) -> float:
        return self._ticks * SIMULATION_STEP

    def cycle_speed(self) -> None:
        self.speed = SPEEDS[(SPEEDS.index(self.speed) + 1) % len(SPEEDS)]

    def advance_generation(self) -> bool:
        """Allow manual breeding within the configured generation limit."""
        if self.finished or not self.world.advance_generation():
            return False
        self._accumulator = 0.0
        return True

    def restart(self, seed: int | None = None) -> None:
        self.world.regenerate_population(seed)
        self._accumulator = 0.0
        self._ticks = 0

    def update(self, dt: float) -> None:
        """Scale elapsed time, preserving every fixed tick across generation changes."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Simulation time must be finite and non-negative.")
        if self.world.paused or self.finished or dt == 0:
            return
        scaled_time = dt * self.speed
        if not math.isfinite(scaled_time):
            raise ValueError("Scaled simulation time must be finite.")
        self._accumulator += scaled_time
        while self._accumulator + 1e-12 >= SIMULATION_STEP:
            if self.finished:
                self._accumulator = 0.0
                break
            if self.world.final_evaluation is not None:
                if not self.auto_advance or not self.world.advance_generation():
                    self._accumulator = 0.0
                    break
            self.world.update(SIMULATION_STEP)
            self._ticks += 1
            self._accumulator = max(0.0, self._accumulator - SIMULATION_STEP)

    def report(self) -> dict:
        """Return serializable observations; incomplete generations are excluded."""
        world = self.world
        return {
            "format_version": 2,
            "seed": world.seed,
            "controller": world.controller,
            "evolution_enabled": world.evolution_enabled,
            "population_size": world.population_size,
            "food_count": world.food_count,
            "arena_size": [world.width, world.height],
            "food_sensor_mode": world.food_sensor_mode,
            "mutation_rate": world.mutation_rate,
            "mutation_scale": world.mutation_scale,
            "simulation_step_seconds": SIMULATION_STEP,
            "generation_limit": self.generation_limit,
            "completed_generations": len(world.generation_stats),
            "total_simulated_seconds": self.total_simulated_seconds,
            "generations": [
                {**asdict(stats), "food_facing_fraction": stats.food_facing_fraction,
                 "survival_rate": stats.survival_rate}
                for stats in world.generation_stats
            ],
        }
