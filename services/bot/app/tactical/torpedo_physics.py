import math

class TorpedoPhysics:
    @staticmethod
    def calculate_muzzle_velocity(tube_length_m: float) -> float:
        """
        Calculates initial velocity in fraction of c.
        Standard Railgun/Coilgun Formula: v = sqrt(2 * a * d)
        Assuming a = 15,000 km/s^2 for a Mark 25 launcher.
        """
        accel = 15000000 
        v_mps = math.sqrt(2 * accel * tube_length_m)
        v_c = v_mps / 299792458
        return round(v_c, 4)

    @staticmethod
    def calculate_impact_yield(launch_yield_iso: float, range_km: float, target_velocity_mps: float) -> tuple:
        """
        Calculates effective yield at impact.
        Yield decays due to containment field degradation over time/distance.
        Returns: (effective_yield, status)
        """
        # Decay constant: 2% per 10,000 km
        decay_factor = 1.0 - (range_km / 10000.0 * 0.02)
        effective_yield = launch_yield_iso * max(0.5, decay_factor)
        
        # Intercept status
        status = "CRITICAL_HIT" if range_km < 5000 else "IMPACT_CONFIRMED"
        return round(effective_yield, 2), status
