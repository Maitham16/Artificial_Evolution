"""A tiny NumPy neural network for sensory input and movement decisions."""

from __future__ import annotations

import math

import numpy as np

from perception import VISION_RANGE  # Re-export the existing sensing-range constant.


INPUT_SIZE = 8
HIDDEN_SIZE = 8
OUTPUT_SIZE = 2
DEFAULT_MUTATION_RATE = 0.1
DEFAULT_MUTATION_SCALE = 0.1
MAX_TURN_RATE = math.pi / 2
SENSOR_NAMES = (
    "food_proximity", "food_direction", "food_visible", "hunger",
    "wall_forward", "wall_right", "wall_back", "wall_left",
)


def validate_mutation_parameters(rate: float, scale: float) -> None:
    if not math.isfinite(rate) or not 0 <= rate <= 1:
        raise ValueError("Mutation rate must be between 0 and 1.")
    if not math.isfinite(scale) or scale < 0:
        raise ValueError("Mutation scale must be finite and non-negative.")


class NeuralNetwork:
    """An 8–8–2 network whose forward pass leaves parameters unchanged."""

    def __init__(self, rng: np.random.Generator) -> None:
        self.input_weights = rng.normal(
            0.0, 1.0 / math.sqrt(INPUT_SIZE), (INPUT_SIZE, HIDDEN_SIZE)
        )
        self.hidden_bias = rng.normal(0.0, 0.1, HIDDEN_SIZE)
        self.output_weights = rng.normal(
            0.0, 1.0 / math.sqrt(HIDDEN_SIZE), (HIDDEN_SIZE, OUTPUT_SIZE)
        )
        self.output_bias = rng.normal(0.0, 0.1, OUTPUT_SIZE)

    @property
    def parameters(self) -> tuple[np.ndarray, ...]:
        return (
            self.input_weights, self.hidden_bias,
            self.output_weights, self.output_bias,
        )

    @property
    def parameter_count(self) -> int:
        return sum(parameter.size for parameter in self.parameters)

    def copy(self) -> NeuralNetwork:
        """Clone all weights and biases into independent arrays."""
        if not all(np.all(np.isfinite(parameter)) for parameter in self.parameters):
            raise ValueError("A parent brain must have finite parameters.")
        child = object.__new__(NeuralNetwork)
        child.input_weights = self.input_weights.copy()
        child.hidden_bias = self.hidden_bias.copy()
        child.output_weights = self.output_weights.copy()
        child.output_bias = self.output_bias.copy()
        return child

    def mutated_copy(
        self, rng: np.random.Generator, *,
        mutation_rate: float = DEFAULT_MUTATION_RATE,
        mutation_scale: float = DEFAULT_MUTATION_SCALE,
    ) -> NeuralNetwork:
        """Create an offspring brain with independent Gaussian mutations."""
        validate_mutation_parameters(mutation_rate, mutation_scale)
        child = self.copy()
        if mutation_rate == 0 or mutation_scale == 0:
            return child
        for parameter in child.parameters:
            mask = rng.random(parameter.shape) < mutation_rate
            parameter[mask] += rng.normal(0.0, mutation_scale, int(np.count_nonzero(mask)))
        if not all(np.all(np.isfinite(parameter)) for parameter in child.parameters):
            raise ValueError("Mutation produced non-finite brain parameters.")
        return child

    def forward(self, sensors: np.ndarray) -> np.ndarray:
        """Return signed turn and throttle commands in [-1, 1]."""
        sensors = np.asarray(sensors, dtype=np.float64)
        if sensors.shape != (INPUT_SIZE,) or not np.all(np.isfinite(sensors)):
            raise ValueError("A brain requires eight finite sensory inputs.")
        hidden = np.tanh(sensors @ self.input_weights + self.hidden_bias)
        outputs = np.tanh(hidden @ self.output_weights + self.output_bias)
        if not np.all(np.isfinite(outputs)):
            raise ValueError("The brain produced a non-finite movement command.")
        return outputs

    def __eq__(self, other: object) -> bool:
        """Compare seeded brains without ambiguous NumPy array comparisons."""
        if not isinstance(other, NeuralNetwork):
            return NotImplemented
        return all(
            np.array_equal(left, right)
            for left, right in zip(self.parameters, other.parameters)
        )
