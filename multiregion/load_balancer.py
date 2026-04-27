import threading
import time
import random
from collections import defaultdict


class LoadBalancer:
    """
    Capacity-aware dynamic load balancer implementing hysteresis-based
    routing redirection as described in Algorithm 2 of the S-Edge paper.

    Key design decisions:
    - alpha (hysteresis factor): prevents routing oscillation by requiring
      the target region to carry less than (alpha * 100)% of the source
      region's load before any redirection occurs.
    - load_threshold: the byte-level trigger operationalising the 80%
      capacity policy.
    - Redistribution is implemented as ROUTING REDIRECTION for new traffic,
      NOT as physical transfer of existing load. This matches Algorithm 2
      exactly: the load balancer returns a target region; the caller routes
      new packets there.
    """

    def __init__(self, regions, alpha=0.7, load_threshold=1000):
        """
        Parameters
        ----------
        regions : list[str]
            Names of the simulated edge regions.
        alpha : float
            Hysteresis factor in (0, 1). Redistribution is triggered only
            when load(r_opt) < alpha * load(r_src). Default 0.7 enforces a
            minimum 30% capacity advantage before any migration occurs.
        load_threshold : int
            Byte-level rebalancing trigger (L_thresh). Operationalises the
            80% capacity policy: redistribution fires before saturation.
        """
        self.regions = regions
        self.region_loads = {region: 0 for region in regions}
        self.alpha = alpha                      # hysteresis factor alpha
        self.load_threshold = load_threshold    # L_thresh in bytes
        self.lock = threading.RLock()

        # Counters for benchmarking
        self.threshold_violations = 0
        self.redirect_events = 0

    # ------------------------------------------------------------------
    # PARAMETER-DRIVEN SIMULATION: 4G/LTE Edge Network Latency Model
    # Inter-region latency ~ N(mu=50ms, sigma=15ms), floored at 10ms.
    # Source: documented 4G backhaul characteristics.
    # ------------------------------------------------------------------
    def _simulate_network_cost(self):
        latency = random.gauss(0.050, 0.015)
        if latency < 0.010:
            latency = 0.010
        time.sleep(latency)
        return latency

    def get_optimal_region(self):
        """Return the region with the minimum current load (arg min)."""
        with self.lock:
            return min(self.region_loads.items(), key=lambda x: x[1])[0]

    def get_target_region(self, current_region):
        """
        Core routing decision implementing Eq. (2) and Eq. (3).

        Returns the region to which new traffic should be directed.
        If the current region is not overloaded, returns current_region.
        If overloaded, checks hysteresis condition before redirecting.

        This is a ROUTING decision for new packets only. No existing load
        is physically moved. Matches Algorithm 2 line-for-line.
        """
        with self.lock:
            current_load = self.region_loads[current_region]

            # Check if current region is overloaded (Eq. 1)
            if current_load <= self.load_threshold:
                return current_region

            # Record threshold violation for benchmarking
            self.threshold_violations += 1

            # Find optimal target: r_opt = arg min L_j(t) (Eq. 2)
            r_opt = min(self.region_loads.items(), key=lambda x: x[1])[0]
            load_opt = self.region_loads[r_opt]

            # Hysteresis check (Eq. 3): redirect only if target has
            # sufficient capacity advantage (at least 1-alpha = 30%)
            if r_opt != current_region and load_opt < self.alpha * current_load:
                self.redirect_events += 1
                return r_opt

            # Hysteresis condition not met: stay in current region
            return current_region

    def update_load(self, region, data_size):
        """
        Update the load metric L_i(t) for the given region.
        L_i(t) = cumulative size of encrypted data (bytes) routed to r_i,
        as defined in Section 6.2.
        """
        with self.lock:
            self.region_loads[region] += data_size

    def simulate_processing(self, processing_rate):
        """
        Simulate per-step data processing draining load from each region.
        """
        with self.lock:
            for region in self.regions:
                self.region_loads[region] = max(
                    0, self.region_loads[region] - processing_rate
                )

    def reset_counters(self):
        """Reset benchmark counters between experimental runs."""
        with self.lock:
            self.threshold_violations = 0
            self.redirect_events = 0
            self.region_loads = {region: 0 for region in self.regions}
