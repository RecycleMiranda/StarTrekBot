# STARFLEET COMMAND - MARS STATION DEFENSE (MSD)
## VOL 06: CAUSAL LOGIC & SIMULATION CORE
**Classification: SECRET / ALGORITHM ONLY**
**English Language Standard**

> [!CAUTION]
> **BOT PHYSICS ENGINE**
> This module is the "Brain" of the simulation. It defines **Consequence**.
> Users do not query this file directly. The Bot uses it to determine *what happens next*.

---

## 1.0 THE FIVE SYSTEM STATES

Every component in the station (defined in Vols 01-03) exists in one of five states:

| State | Color Code | Definition | Simulator Logic |
| :--- | :--- | :--- | :--- |
| **NOMINAL** | **GREEN** | 100% Efficiency. | `Reply("Systems functional.")` |
| **STRESSED** | **BLUE** | 80-99%. High load. | `Reply("EPS grid stabilizing at 98%.")` |
| **DEGRADED** | **YELLOW** | 50-79%. Reduced capability. | `Reply("Warning: Power output down to 60%.")` |
| **CRITICAL** | **RED** | 1-49%. Imminent failure. | `Reply("ALERT: Structure failing. Evacuate deck.")` |
| **OFFLINE** | **GREY** | 0%. Dead. | `Reply("System non-responsive.")` |

---

## 2.0 FAILURE CASCADES (The "Domino Effect")

### 2.1 POWER CASCADE (Source: 02_Power_Extended.md)
*   **Trigger**: M/ARA Cooling Failure (Blue line rupture).
*   **Step 1 (T+0s)**: Reaction Chamber Temp rises > 1M Kelvin.
*   **Step 2 (T+30s)**: Computer attempts `Emergency_SCRAM()`.
    *   *If SCRAM Fails*: Proceed to Step 3.
*   **Step 3 (T+120s)**: Dilithium Crystal fractures (Decrystallization).
*   **Step 4 (T+300s)**: Magnetic Constriction Fails. **CORE BREACH**.
*   **Bot Output**: *"Warning. Warp Core breach in 5 minutes. Ejection systems online."*

### 2.2 DEFENSE CASCADE (Source: 03_Tactical_Extended.md)
*   **Trigger**: Incoming Phaser impact (Yield > 500 GW).
*   **Layer 1 (Shields)**: Absorbs 90% of energy.
    *   *If Shield < 20%*: Bleed-through occurs.
*   **Layer 2 (SIF)**: Absorbs physical shock.
    *   *If SIF Overload*: EPS conduits explode on the bridge.
*   **Layer 3 (Hull)**: Armor ablation.
    *   *Effect*: Decompression on affected decks.
*   **Bot Output**: *"Shields down to 15%. Hull breach on Deck 42. SIF field holding."*

---

## 3.0 RESOURCE LOGIC

### 3.1 REPLICATION QUOTA
*   **Cost**: 1kg Matter = 5 MJ Energy.
*   **Logic**:
    *   `IF (Alert_Status == RED)`: Replicators are **LOCKED** to Medical/Industrial use only.
    *   *User Request*: "One Coffee, Black."
    *   *Bot Reply*: "Negative. Replicators restricted to emergency rations only."

### 3.2 TRANSPORTER WINDOWS
*   **Logic**: Transporters cannot penetrate **Shields**.
    *   *Scenario*: User asks to beam up a team while shields are up.
    *   *Bot Reply*: "Unable to comply. You must lower shields to initiate transport."
    *   *Override*: "Blind Beam-Through" (Risk of signal scattering).

---

## 4.0 SECURITY RESPONSE MATRIX

| Intruder Threat | Response Protocol | Bot Action |
| :--- | :--- | :--- |
| **Unarmed / Confused** | Level 1 (Monitor) | Track location via internal sensors. |
| **Armed / Hostile** | Level 3 (Contain) | Lock blast doors. Erect force fields. |
| **Borg / Super-Human** | Level 5 (Neutralize) | Vent section to space OR flood with Anesthezine gas. |

---

> **END OF LOGIC CORE**
