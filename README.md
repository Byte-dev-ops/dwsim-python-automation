# DWSIM Python Automation — Screening Task

This project demonstrates fully automated, headless simulation of process flowsheets in DWSIM using Python. The workflow programmatically constructs and evaluates a Plug Flow Reactor (PFR) and a rigorous distillation column, followed by parametric sweep studies.

---

## 1. Setup

### Requirements

* **Python Version:** 3.10 or 3.11 (recommended for `pythonnet` compatibility)
* **DWSIM Version:** 8.x (standard Windows installation)

### Dependencies

Install required Python libraries:

```bash
pip install -r requirements.txt
```

### Running the Script

```bash
python run_screening.py
```

* The simulation runs **completely headless** (no GUI interaction).
* Progress is logged to console and `simulation.log`.
* Results are continuously written to `results.csv`.

---

## Demo

🎥 [Watch Demo Video](your_drive_link_here)

This video demonstrates:
- Headless execution of the automation script  
- Parametric sweep in real time  
- Generated outputs (CSV and plots)  

---

## 2. Workflow Overview

### 2.1 Flowsheet Construction

* Uses DWSIM **Automation3 API** via `pythonnet`
* No prebuilt flowsheets or GUI usage
* Programmatically creates:

  * Property package (Peng-Robinson)
  * Material and energy streams
  * Reaction set (n-pentane isomerization)
  * Unit operations:

    * Plug Flow Reactor (`RCT_PFR`)
    * Rigorous Distillation Column (`RigorousColumn`)

---

### 2.2 Parametric Sweep

#### Part A & C — PFR Study

* Variables:

  * Reactor Volume: 0.5 → 10 m³
  * Temperature: 350 → 450 K
* Total cases: **25**

#### Part B & C — Distillation Column Study

* Variables:

  * Reflux Ratio: 1.2 → 4.0
  * Number of Stages: 10 → 25
* Total cases: **20**

---

## 3. Assumptions

* **Isothermal PFR:** Reactor temperature is fixed; DWSIM computes heat duty required to maintain isothermal conditions.
* **Property Package:** **Peng-Robinson (PR)** — suitable for non-polar hydrocarbon systems and VLE prediction.
* **Reaction Model:** First-order kinetic model for n-pentane isomerization:

  * Pre-exponential factor: (1.2 \times 10^8 , s^{-1})
  * Activation energy: (65 , kJ/mol)

---

### Execution Snapshot

Below is a sample terminal output demonstrating fully automated, headless execution of the simulation workflow:

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/ecb24052-7d37-4314-b173-26223e7196cb" height="300"/></td>
    <td><img src="https://github.com/user-attachments/assets/3d843886-6af3-4567-b287-5edf996eaa41" height="300"/></td>
  </tr>
</table>

**Highlights:**
- Headless execution using DWSIM Automation API (no GUI interaction)  
- Automated parametric sweep across PFR and distillation column cases  
- Real-time logging of simulation progress and outputs  
- Successful execution of all simulation cases without failure
  
---

## 4. Outputs

### 4.1 results.csv

Contains all simulation cases (45 total) with:

<div align="center">
 <img width="700" height="856" alt="image" src="https://github.com/user-attachments/assets/55ec0bdf-2003-493c-8643-479d84615066" />

</div>

This dataset includes:
- Input parameters  
- Simulation outputs  
- Success flags and error handling  

**Metadata**

* `case_type`, `success_flag`, `error_message`

**Input Variables**

* `V`, `T`, `RR`, `N`

**Key Performance Indicators (KPIs)**

* `conversion`
* `distillate_purity`
* `nC5_outlet_flow`
* `iC5_outlet_flow`
* `temperature_out`
* `heat_duty`
* `condenser_duty`
* `reboiler_duty`

---

### 4.2 Plots (plots/ directory)

Generated visualizations showing parametric trends:

<div align="center">
 <img width="600" height="657" alt="image" src="https://github.com/user-attachments/assets/99faa397-d0be-4d90-90be-987acc071fca" />
 <img width="600" height="657" alt="image" src="https://github.com/user-attachments/assets/8b2463c7-969c-4b61-9cf8-6fa5fe908f01" />


</div>

**Insights from plots:**
- Conversion increases with temperature and reactor volume  
- Distillation purity improves with reflux ratio  
- Energy consumption increases with separation performance  

1. **pfr_conversion_vs_volume.png**
   Effect of reactor size on conversion

2. **pfr_conversion_vs_temperature.png**
   Temperature dependence of reaction kinetics

3. **col_purity_vs_reflux.png**
   Impact of reflux ratio on separation

4. **col_duty_vs_stages.png**
   Energy requirement vs number of stages

---

## 5. Engineering Insights

* **Reaction Kinetics:** Conversion increases strongly with temperature due to Arrhenius dependence.
* **Reactor Design:** Larger reactor volumes increase residence time, improving conversion at lower temperatures.
* **Thermodynamic Limitation:** Separation of n-pentane and isopentane is difficult due to close boiling points (~10°C difference).
* **Column Behavior:** Increasing reflux ratio improves purity but significantly increases energy consumption.
* **Optimal Trade-off:** High purity requires both higher reflux and more stages, leading to diminishing returns.

---

## 6. Key Features

* Fully **headless simulation** (no GUI)
* **Programmatic flowsheet construction**
* Robust **error handling and logging**
* Automated **parametric sweep execution**
* Structured **data export and visualization**

---

## 7. File Structure

```
project/
│── run_screening.py
│── requirements.txt
│── README.md
│── results.csv
│── simulation.log
│── simulation_report.txt
│── plots/
```

---

## 8. Notes

* All simulations executed successfully (45/45 cases).
* The workflow is scalable for larger screening and optimization studies.

---

## 9. Summary

This project demonstrates the ability to:

- Build complete process flowsheets programmatically using DWSIM Automation API  
- Perform headless simulation without GUI interaction  
- Implement parametric sweeps for reactor and separation units  
- Extract and analyze key engineering performance metrics  
- Generate structured outputs and visualizations  

The work reflects a strong integration of process engineering fundamentals with Python-based automation.


## Additional Note

The separation of n-pentane and isopentane is thermodynamically limited due to their close boiling points. This is reflected in the simulation results where purity plateaus despite increasing reflux ratio and stages.
