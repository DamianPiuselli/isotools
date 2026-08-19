"""
Dual Isotope Water Analysis Example & ISO 17025 Report Generator

Demonstrates how to process EA-IRMS water isotope data (2H and 18O) using isotools:
1. Generates synthetic raw sequence data with linear drift and bad data anomalies.
2. Registers drift monitors and quantifies analytical drift trend.
3. Applies linear drift correction using 'Buenos Aires_H' / 'Buenos Aires_O'.
4. Performs automated QA/QC diagnostic inspection to review warning logs.
5. Applies transparent sample exclusions based on warning logs.
6. Calibrates to V-SMOW scale via MultiPointLinear regression.
7. Exports single-isotope and dual-isotope ISO 17025 audit reports (HTML & Excel).
"""

import os
from generate_synthetic_water_data import generate_synthetic_data
from isotools import WATER_H, WATER_O, Batch, MultiPointLinear, generate_dual_isotope_html_report


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    excel_path = os.path.join(script_dir, "synthetic_water_sequence.xlsx")

    # 1. Regenerate synthetic data with linear drift and bad data anomalies
    generate_synthetic_data(excel_path)

    print("\n" + "=" * 60)
    print("EXECUTING DUAL ISOTOPE WATER PROCESSING WORKFLOW")
    print("=" * 60)

    # 2. Load Batches
    batch_h = Batch(excel_path, WATER_H, sheet_name="2H.wke")
    batch_o = Batch(excel_path, WATER_O, sheet_name="18O.wke")

    # 3. Register Drift Monitor Standards
    print("\n[Drift Analysis] Registering 'Buenos Aires_H' / 'Buenos Aires_O' as drift monitors...")
    batch_h.set_drift_monitors(["Buenos Aires_H"])
    batch_o.set_drift_monitors(["Buenos Aires_O"])

    # Quantify raw analytical drift trend
    drift_h = batch_h.check_drift()
    drift_o = batch_o.check_drift()

    print("\n📈 2H Raw Drift Rate:")
    print(drift_h)

    print("\n📈 18O Raw Drift Rate:")
    print(drift_o)

    # Apply Linear Drift Correction
    print("\n[Drift Correction] Applying linear drift correction using 'Buenos Aires' monitors...")
    batch_h.apply_drift_correction("Buenos Aires_H")
    batch_o.apply_drift_correction("Buenos Aires_O")

    # 4. Inspect Automated QA/QC Warning Logs
    print("\n" + "-" * 60)
    print("⚠️ AUTOMATED DIAGNOSTIC WARNING LOGS:")
    print("-" * 60)

    print("\n[2H Diagnostic Warnings]:")
    print(batch_h.alerts.to_string(index=False) if not batch_h.alerts.empty else "No alerts.")

    print("\n[18O Diagnostic Warnings]:")
    print(batch_o.alerts.to_string(index=False) if not batch_o.alerts.empty else "No alerts.")

    # 5. Audit Decisions: Exclude problematic sample rows based on warning logs
    print("\n" + "-" * 60)
    print("📋 AUDIT DECISIONS: SAMPLE EXCLUSIONS BASED ON WARNING LOGS:")
    print("-" * 60)
    print("  - 2H: Exclusions applied for Row 22 (low amplitude signal drop) and Row 30 (double drop area anomaly)")
    batch_h.exclude_rows([22, 30])

    print("  - 18O: Exclusion applied for Row 16 (extreme delta outlier spike / high variance)")
    batch_o.exclude_rows([16])

    # 6. Register Primary Calibration Anchors
    anchors_h = ["Mar_H", "Buenos Aires_H", "Mendoza_H", "Antartida_H"]
    anchors_o = ["Mar_O", "Buenos Aires_O", "Mendoza_O", "Antartida_O"]

    batch_h.set_anchors(anchors_h)
    batch_o.set_anchors(anchors_o)

    # 7. Fit V-SMOW Scale Calibrations
    print("\n[Calibration] Fitting MultiPointLinear calibrations to V-SMOW scale...")
    batch_h.process(MultiPointLinear())
    batch_o.process(MultiPointLinear())

    print("\n=== 2H PROCESSED RESULTS SUMMARY ===")
    print(batch_h.report.head(10))

    print("\n=== 18O PROCESSED RESULTS SUMMARY ===")
    print(batch_o.report.head(10))

    # 8. Export Reports with 5-Stage Lineage Audit & Warning Logs
    h_html = os.path.join(script_dir, "Synthetic_Water_2H_Report.html")
    o_html = os.path.join(script_dir, "Synthetic_Water_18O_Report.html")
    h_xlsx = os.path.join(script_dir, "Synthetic_Water_2H_Report.xlsx")
    o_xlsx = os.path.join(script_dir, "Synthetic_Water_18O_Report.xlsx")
    dual_html = os.path.join(script_dir, "Synthetic_Water_Dual_Isotope_Report.html")

    batch_h.save_html_report(h_html)
    batch_o.save_html_report(o_html)
    batch_h.save_report(h_xlsx)
    batch_o.save_report(o_xlsx)

    generate_dual_isotope_html_report(
        batch_h,
        batch_o,
        dual_html,
        title="Synthetic Water Dual Isotope (2H & 18O) Audit Report",
    )

    print("\n" + "=" * 60)
    print("REPORTS GENERATED SUCCESSFULLY WITH DRIFT & AUDIT LINEAGE:")
    print(f"  - 2H HTML Audit Report   : {h_html}")
    print(f"  - 18O HTML Audit Report  : {o_html}")
    print(f"  - Dual Isotope Report    : {dual_html}")
    print(f"  - 2H Excel Data Report   : {h_xlsx}")
    print(f"  - 18O Excel Data Report  : {o_xlsx}")
    print("=" * 60)


if __name__ == "__main__":
    main()
