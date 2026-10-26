"""Conservative food-collision broad phase for large matched evaluations.

World still controls movement, sensing, energy, death, and replenishment. The
original scalar circle test and ownership key decide every possible contact.
"""

import numpy as np

from world import World


class EvaluationWorld(World):
    def _resolve_food_collisions(self):
        eaten = set()
        if self.creatures and self.food:
            food = np.array([(f.x, f.y, f.radius) for f in self.food])
            bodies = np.array([(c.x, c.y, c.radius) for c in self.creatures])
            dx = food[:, 0, None] - bodies[None, :, 0]
            dy = food[:, 1, None] - bodies[None, :, 1]
            # Include a numerical margin; the scalar test below rejects any
            # false positive, including points just outside a tangent circle.
            near = dx * dx + dy * dy <= (food[:, 2, None] + bodies[None, :, 2]) ** 2 + 1e-9
            candidates = {}
            for fi, ci in zip(*np.nonzero(near)):
                candidates.setdefault(int(fi), []).append(self.creatures[int(ci)])
            # nonzero visits food rows in original order. Energy/capacity must
            # be checked here because earlier meals can fill an actor's stock.
            for i, actors in candidates.items():
                pellet = self.food[i]
                eater = min((c for c in actors if c.alive and c.energy < c.energy_capacity
                             and pellet.overlaps_circle(c.x, c.y, c.radius)),
                            key=lambda c: ((c.x - pellet.x) ** 2 + (c.y - pellet.y) ** 2, c.creature_id),
                            default=None)
                if eater is not None and eater.eat(pellet):
                    eaten.add(i)
                    self.total_food_eaten += 1
        self.food = [pellet for i, pellet in enumerate(self.food) if i not in eaten]
        # Preserve food order and every scalar rejection-sampling RNG draw.
        for _ in range(self.food_count - len(self.food)):
            self.food.append(self._spawn_food())
