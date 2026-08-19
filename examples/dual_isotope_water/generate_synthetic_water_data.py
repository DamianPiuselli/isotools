"""
Synthetic Data Generator for Water Isotope Dual Analysis Example (2H & 18O)

Generates an Excel workbook 'synthetic_water_sequence.xlsx' mimicking raw Isodat EA-IRMS exports.
Features:
- Systematic instrumental linear drift across the sequence (+0.04 ‰/row for 2H, +0.008 ‰/row for 18O)
- Periodically spaced drift monitor standards ('Buenos Aires_H' / 'Buenos Aires_O')
- Calibration anchors ('Mar', 'Buenos Aires', 'Mendoza', 'Antartida')
- Environmental water sample replicates ('River_Water_01..04', 'Rain_Water_01..04')
- Injected bad data anomalies to trigger isotools QA/QC warning logs:
  1. Row 16: High-variance delta outlier in 18O (integration/contamination artifact)
  2. Row 22: Low amplitude / signal loss in 2H (partial injection)
  3. Row 30: Response factor / area anomaly in 2H (double drop / weighing error)
"""

import os
import numpy as np
import pandas as pd


def generate_synthetic_data(output_path: str = "synthetic_water_sequence.xlsx"):
    np.random.seed(42)  # For reproducible synthetic data

    # 1. Define sequence sample layout
    sequence = [
        # Initial Anchors & Drift Monitors
        ("Mar_H", "Mar_O", 0.0, 0.0),
        ("Mar_H", "Mar_O", 0.0, 0.0),
        ("Buenos Aires_H", "Buenos Aires_O", -38.5, -6.0),  # Monitor 1
        ("Buenos Aires_H", "Buenos Aires_O", -38.5, -6.0),  # Monitor 2
        ("Mendoza_H", "Mendoza_O", -72.0, -11.4),
        ("Mendoza_H", "Mendoza_O", -72.0, -11.4),
        ("Antartida_H", "Antartida_O", -94.0, -12.5),
        ("Antartida_H", "Antartida_O", -94.0, -12.5),
        # Environmental Unknown Samples (Batch 1)
        ("River_Water_01", "River_Water_01", -45.0, -6.8),
        ("River_Water_01", "River_Water_01", -45.2, -6.9),
        ("River_Water_02", "River_Water_02", -52.1, -7.6),
        ("River_Water_02", "River_Water_02", -51.8, -7.5),
        ("Rain_Water_01", "Rain_Water_01", -18.4, -3.2),
        ("Rain_Water_01", "Rain_Water_01", -18.7, -3.1),
        ("Rain_Water_02", "Rain_Water_02", -28.0, -4.5),
        ("Rain_Water_02", "Rain_Water_02", -27.8, -4.4),  # Row 16
        # Mid-sequence Anchor check & Drift Monitors
        ("Buenos Aires_H", "Buenos Aires_O", -38.5, -6.0),  # Monitor 3
        ("Buenos Aires_H", "Buenos Aires_O", -38.5, -6.0),  # Monitor 4
        # Environmental Unknown Samples (Batch 2)
        ("River_Water_03", "River_Water_03", -65.4, -9.2),
        ("River_Water_03", "River_Water_03", -65.1, -9.3),
        ("River_Water_04", "River_Water_04", -78.3, -11.0),
        ("River_Water_04", "River_Water_04", -78.0, -10.9),  # Row 22
        ("Rain_Water_03", "Rain_Water_03", -12.3, -2.1),
        ("Rain_Water_03", "Rain_Water_03", -12.0, -2.2),
        ("Rain_Water_04", "Rain_Water_04", -32.5, -5.1),
        ("Rain_Water_04", "Rain_Water_04", -32.1, -5.0),
        # Final Anchor & Drift Monitor Verification
        ("Buenos Aires_H", "Buenos Aires_O", -38.5, -6.0),  # Monitor 5
        ("Buenos Aires_H", "Buenos Aires_O", -38.5, -6.0),  # Monitor 6
        ("Mar_H", "Mar_O", 0.0, 0.0),
        ("Mar_H", "Mar_O", 0.0, 0.0),
        ("Mendoza_H", "Mendoza_O", -72.0, -11.4),
        ("Mendoza_H", "Mendoza_O", -72.0, -11.4),
        ("Antartida_H", "Antartida_O", -94.0, -12.5),
        ("Antartida_H", "Antartida_O", -94.0, -12.5),
    ]

    rows_h = []
    rows_o = []

    slope_h_raw, intercept_h_raw = 0.985, 2.5  # Raw machine offset for 2H
    slope_o_raw, intercept_o_raw = 1.020, -1.2  # Raw machine offset for 18O

    # Linear drift rates per injection row
    drift_h_rate = 0.045  # +0.045 ‰ per row
    drift_o_rate = 0.008  # +0.008 ‰ per row

    for idx, (name_h, name_o, true_2h, true_18o) in enumerate(sequence, start=1):
        # Base raw measurements with minor instrument noise + systematic linear drift
        noise_h = np.random.normal(0, 0.3)
        noise_o = np.random.normal(0, 0.06)

        drift_h = idx * drift_h_rate
        drift_o = idx * drift_o_rate

        raw_2h = (true_2h * slope_h_raw + intercept_h_raw) + drift_h + noise_h
        raw_18o = (true_18o * slope_o_raw + intercept_o_raw) + drift_o + noise_o

        amp_2 = int(np.random.normal(2800, 100))
        area_2 = round(amp_2 * 0.009, 3)

        amp_28 = int(np.random.normal(5100, 150))
        area_28 = round(amp_28 * 0.011, 3)

        # ----------------------------------------------------
        # INJECT BAD DATA ANOMALIES FOR QA/QC SHOWCASE:
        # ----------------------------------------------------
        # Anomaly 1: Row 16 (Rain_Water_02) in 18O - High Delta Outlier (spike to +45.2 ‰)
        if idx == 16:
            raw_18o = 45.200

        # Anomaly 2: Row 22 (River_Water_04) in 2H - Low Amplitude / Signal Loss
        if idx == 22:
            amp_2 = 80  # Far below normal 2800 mV

        # Anomaly 3: Row 30 (Mendoza_H) in 2H - Double Drop / Area Response Factor Anomaly
        if idx == 30:
            area_2 = round(area_2 * 2.4, 3)  # 2.4x expected area

        rows_h.append({
            "Row": idx,
            "Identifier 1": name_h,
            "Identifier 2": f"ID-{1000+idx}",
            "Peak Nr": 3,
            "d 3H2/2H2": round(raw_2h, 3),
            "Ampl 2": amp_2,
            "Area 2": area_2,
            "Date": "08/19/2026",
            "Time": f"{10 + idx//60:02d}:{idx%60:02d}:00",
        })

        rows_o.append({
            "Row": idx,
            "Identifier 1": name_o,
            "Identifier 2": f"ID-{1000+idx}",
            "Peak Nr": 4,
            "d 18O/16O": round(raw_18o, 3),
            "Ampl 28": amp_28,
            "Area 28": area_28,
            "Date": "08/19/2026",
            "Time": f"{10 + idx//60:02d}:{idx%60:02d}:00",
        })

    df_h = pd.DataFrame(rows_h)
    df_o = pd.DataFrame(rows_o)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_h.to_excel(writer, sheet_name="2H.wke", index=False)
        df_o.to_excel(writer, sheet_name="18O.wke", index=False)

    print(f"✅ Generated synthetic water isotope dataset: '{output_path}'")
    print(f"   - 2H Sheet  : 2H.wke ({len(df_h)} rows)")
    print(f"   - 18O Sheet : 18O.wke ({len(df_o)} rows)")
    print("   - Systematic Instrumental Drift Injected:")
    print("     * 2H drift rate : +0.045 ‰ per row")
    print("     * 18O drift rate: +0.008 ‰ per row")
    print("   - Injected Bad Data Anomalies:")
    print("     * Row 16 (18O): Extreme delta outlier (+45.2 ‰)")
    print("     * Row 22 (2H): Low amplitude signal drop (80 mV)")
    print("     * Row 30 (2H): Response factor double-drop area anomaly")


if __name__ == "__main__":
    generate_synthetic_data()
