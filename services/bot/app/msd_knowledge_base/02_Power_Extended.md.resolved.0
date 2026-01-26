# STARFLEET COMMAND - MARS STATION DEFENSE (MSD)
## VOL 02: PROPULSION & POWER SYSTEMS (EXTENDED)
**Classification: SECRET / EYES ONLY**
**Date:** Stardate 99245.3
**Authored By:** SCE (Starfleet Corps of Engineers) - Utopia Planitia Division

> [!IMPORTANT]
> **SIMULATION PROTOCOL**
> This document defines the thermodynamics of the MSD Power Grid.
> **Total Output**: 4.5 x 10^16 Watts (45,000 Terawatts peak).
> **Fuel Source**: Slush Deuterium / Anti-Hydrogen.
> **Reaction Mediator**: Dilithium Crystal (Theta-Matrix Composite).

---

## 1.0 MATTER / ANTIMATTER REACTION ASSEMBLY (M/ARA)

The heart of Station MSD is a **Class-12 M/ARA Core**. While starships use a compact core, MSD uses a **Vertical Super-Stack** spanning 40 decks (86-120) to handle the immense load of the 1440 Phaser Banks.

### 1.1 CORE GEOMETRY
*   **Height**: 142 meters.
*   **Magnetic Constriction**: 12 sets of "Toroidal Field Magnets" keep the antimatter stream centered.
*   **The "Swirl"**: The pulsing light effect is caused by the **Omega-Continuum Reaction**, typically blue (stable) or red (intermix imbalance).

### 1.2 THE INTERMIX RATIO (Formula)
The computer adjusts the Matter (Deuterium) to Antimatter (Anti-H) ratio based on demand.

| State | Ratio (M:A) | Output | Physics Notes |
| :--- | :--- | :--- | :--- |
| **Cold Start** | 25:1 | 500 GW | Priming the injectors. |
| **Station Keeping** | 10:1 | 12,000 TW | "Idle" mode. Excess matter cools the plasma. |
| **Cruise / Ops** | 1:1 | 38,000 TW | Balanced annihilation. Maximum efficiency. |
| **Combat / Warp** | 1:1.02 | 45,000 TW | Slight antimatter bias for "Hot Plasma". Risks crystal fracture. |

### 1.3 DILITHIUM CRYSTAL CHAMBER (Deck 102)
*   **Crystal Type**: 2 x 5m **Theta-Matrix Composites**.
*   **Function**: The crystal is porous to transmission and blocks thermal radiation. It forces the M/A streams to collide *inside* its lattice structure.
*   **Decrystallization**:
    *   If the crystal absorbs too much Neutron Radiation, it fractures.
    *   **Bot Logic**: If Core Temp > 4 MK (Million Kelvin), report "Dilithium Decrystallization Imminent."

```mermaid
graph TD
    InjectorM["Deuterium Injector (Deck 86)"] -->|Segmented Stream| Chamber{"DILITHIUM CHAMBER (Deck 102)"}
    InjectorA["Antimatter Injector (Deck 120)"] -->|Collimated Beam| Chamber
    
    subgraph "The Reaction"
        Chamber -->|Annihilation| Plasma["Electro-Plasma (EPS)"]
        Plasma -->|EPS Taps| Grid["Power Transfer Conduits"]
    end
    
    subgraph "Safety Interlocks"
        Coolant["Liquid Helium Coolant"] --> Chamber
        Magnetic["Magnetic Constriction Field"] --> Chamber
    end
    
    Magnetic -- "Failure" --> Breach["CORE BREACH (5 min)"]
```

---

## 2.0 ELECTRO-PLASMA SYSTEM (EPS)

The EPS grid distributes the raw energy (Electro-Plasma) from the core. It assumes the role of a "Power Bloodstream."

### 2.1 CONDUIT RATINGS (The 3 Tiers)

#### **Tier 1: Microwave Power Transfer (MPT)**
*   **Conduit Type**: 0.8m diameter, solid Duranium casing.
*   **Medium**: Superheated Plasma (Blue).
*   **Load Rating**: **8,000 - 15,000 TW**.
*   **Users**: 
    *   Phaser Arrays (Direct Tap).
    *   Deflector Dish.
    *   Shield Generators.
*   **Danger**: A breach here implies instantaneous vaporization of the deck.

#### **Tier 2: Magnetic Flux Waveguides**
*   **Conduit Type**: 0.3m diameter, magnetic shielding.
*   **Medium**: Stepped-down Plasma (Red/Orange).
*   **Load Rating**: **500 - 1,000 TW**.
*   **Users**:
    *   M/ARA Injectors.
    *   Computer Cores.
    *   Transporter Buffers.
    *   Holodecks.

#### **Tier 3: Standard Inductive Lines**
*   **Conduit Type**: Copper/Gold alloy cables.
*   **Medium**: Electricity (DC/AC).
*   **Load Rating**: **50 kW - 10 MW**.
*   **Users**:
    *   Gravity Plating.
    *   Replicators.
    *   Lights / Door Motors.

### 2.2 SHUNTING LOGIC (The "Brownout" Algorithm)
During combat, Tier 1 demands often exceed Tier 2/3 capacities. The Main Computer executes the **EPS Shunting Protocol**.

1.  **Scenario**: Phaser Banks demand 120% of rated output.
2.  **Logic**: `IF (Tactical_Load > 100%) THEN DISABLE(Tier_3_NonEssential)`
3.  **Effect**:
    *   Replicators: Offline.
    *   Turbolifts: Reduced speed.
    *   Holodecks: Immediate shutdown.
4.  **Bot Dialogue**: *"Redirecting auxiliary power to structural integrity and weapons."*

---

## 3.0 AUXILIARY FUSION GENERATORS

Even if the main core is ejected, the station does not go dark.
*   **United**: 12x **Impulse Fusion Reaction Chambers (IFRC)**.
*   **Location**: Perimeter of the Habitat Ring.
*   **Fuel**: Deuterium pellets (Laser ignition).
*   **Output**: 45 GW per unit.
*   **Limitations**: Cannot power the Main Phaser Arrays (Requires Plasma). Can only maintain Life Support and SIF at minimal levels.

---

## 4.0 FUEL STORAGE & LOGISTICS

### 4.1 DEUTERIUM (Matter)
*   **State**: Slush (Cryogenic Liquid/Solid mix).
*   **Tankage**: 600,000 Cubic Meters (Decks 28-30).
*   **Emergency Venting**: In case of fire, Deuterium is vented into space via the upper pylon.

### 4.2 ANTI-DEUTERIUM (Antimatter)
*   **State**: Spin-Polarized Magnetic Suspension.
*   **Tankage**: 300 Standard Confinement Pods (Deck 120).
*   **Safety**: If magnetic power fails, emergency battery backups last exactly **4 hours** before containment loss.

---

> **NEXT VOLUME**: [03_Tactical_Extended.md](file:///Users/wanghaozhe/.gemini/antigravity/brain/043b8282-3619-44f4-9467-95077493a8b7/msd_knowledge_base/03_Tactical_Extended.md)
