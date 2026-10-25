"""A tiny NumPy neural network for sensory input and movement decisions."""

import math

import numpy as np

from perception import VISION_RANGE  # Re-export the existing sensing-range constant.


INPUT_SIZE = 8
HIDDEN_SIZE = 8
OUTPUT_SIZE = 2
MAX_TURN_RATE = math.pi / 2
SENSOR_NAMES = (
    "food_proximity", "food_direction", "food_visible", "hunger",
    "wall_forward", "wall_right", "wall_back", "wall_left",
)


class NeuralNetwork:
    """An untrained 8–8–2 network with tanh hidden and output activations."""

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
