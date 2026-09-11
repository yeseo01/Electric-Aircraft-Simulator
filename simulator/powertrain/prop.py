# powertrain/prop.py
from __future__ import annotations
from typing import Tuple
import numpy as np
from scipy.interpolate import interp1d


class PropellerModel:
    """
    Cp(J), eta(J) surrogate 기반 프로펠러 모델

    사용 흐름:
      1) load_surrogate()
      2) evaluate(rpm, V, rho)
    """

    def __init__(
        self,
        Cp_func,
        eta_func,
        Dp: float,
        J_min: float,
        J_max: float,
        V_min_for_thrust: float,
        P_cap_W: float,
        ):
        
        self.Cp_func = Cp_func
        self.eta_func = eta_func
        self.Dp = float(Dp)
        self.J_min = float(J_min)
        self.J_max = float(J_max)
        self.V_min_for_thrust = float(V_min_for_thrust)
        self.P_cap_W = float(P_cap_W)

    @staticmethod
    def load_surrogate(npz_path: str,
                       eta_clip: Tuple[float, float],
                       eta_fallback: float,
                       P_cap_W: float,
                       V_min_for_thrust: float):
        """
        NPZ에서 Cp(J), eta(J) 로드 후 PropellerModel 생성
        """
        data = np.load(npz_path, allow_pickle=True)

        # J grid
        if "J" in data:
            Jg = data["J"].astype(float)
        elif "Jp" in data:
            Jg = data["Jp"].astype(float)
        else:
            raise KeyError("NPZ에 J 또는 Jp가 없습니다.")

        Cpg = data["Cp"].astype(float)

        # eta
        eta_key = None
        for k in ["eta", "Eta", "ETA"]:
            if k in data:
                eta_key = k
                break

        if eta_key is None:
            etag = np.full_like(Jg, eta_fallback, dtype=float)
        else:
            etag = data[eta_key].astype(float)

        Dp = float(data["D_PROP"]) if "D_PROP" in data else 1.64

        # 정렬
        order = np.argsort(Jg)
        Jg = Jg[order]
        Cpg = Cpg[order]
        etag = etag[order]

        # 클립
        Cpg = np.clip(Cpg, 1e-6, 10.0)
        etag = np.clip(etag, eta_clip[0], eta_clip[1])

        Cp_func = interp1d(Jg, Cpg, kind="linear",
                           bounds_error=False,
                           fill_value=(float(Cpg[0]), float(Cpg[-1])))

        eta_func = interp1d(Jg, etag, kind="linear",
                            bounds_error=False,
                            fill_value=(float(etag[0]), float(etag[-1])))

        return PropellerModel(
            Cp_func=Cp_func,
            eta_func=eta_func,
            Dp=Dp,
            J_min=float(np.min(Jg)),
            J_max=float(np.max(Jg)),
            V_min_for_thrust=V_min_for_thrust,
            P_cap_W=P_cap_W,
        )

    # ------------------------------------------------------------
    # main evaluation
    # ------------------------------------------------------------
    def evaluate(self,
                 rpm: float,
                 V_ms: float,
                 rho: float):
        """
        rpm, V, rho → (P_prop, T, J)

        수식:
          n = rpm/60
          J = V/(nD)
          P_prop = rho * n^3 * D^5 * Cp(J)
          T = eta(J) * P_prop / V_eff
        """

        V = float(max(0.0, V_ms))
        rho = float(max(1e-6, rho))
        rpm = float(max(0.0, rpm))

        n = max(1e-3, rpm / 60.0)

        J_raw = V / max(1e-6, n * self.Dp)
        J = float(np.clip(J_raw, self.J_min, self.J_max))

        Cp = float(self.Cp_func(J))
        eta = float(self.eta_func(J))

        P_prop = rho * (n**3) * (self.Dp**5) * Cp
        P_prop = float(np.clip(P_prop, 0.0, self.P_cap_W))

        V_eff = max(V, self.V_min_for_thrust)
        T = eta * P_prop / V_eff

        return float(P_prop), float(T), float(J)
