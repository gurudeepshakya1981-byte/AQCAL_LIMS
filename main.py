from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import psycopg2
from pydantic import BaseModel
import math
import statistics
import json
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = FastAPI(title="AQCAL LIMS")
templates = Jinja2Templates(directory="templates")

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

class CalcRequest(BaseModel):
    template_id: int
    nominal_value: float
    readings_master: list[float]
    readings_test: list[float]
    variables: dict = {}

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Recreate templates table to load all 20 sheets
    cur.execute("DROP TABLE IF EXISTS templates")
    cur.execute("""
        CREATE TABLE templates (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            unit VARCHAR(50),
            formula_json TEXT,
            input_schema TEXT
        )
    """)
    
    # --- ALL 20 TEMPLATES FROM YOUR EXCEL SHEETS ---
    master_templates = [
        # 1. ET: 10 MΩ Resistance
        {
            "name": "ET - 10 MΩ Resistance", "unit": "MΩ",
            "formulas": [
                {"name": "Master Cert (0.005%)", "formula": "(0.005 * {nominal} / 100) / 2"},
                {"name": "Master Acc (0.06%)", "formula": "(0.06 * {nominal} / 100) / sqrt(3)"},
                {"name": "Resolution", "formula": "(0.00001 / 2) / sqrt(3)"}
            ],
            "inputs": []
        },
        # 2. ET: DC Voltage
        {
            "name": "ET - DC Voltage", "unit": "V",
            "formulas": [
                {"name": "Master Uncert", "formula": "{master_uncert} / 2"},
                {"name": "Master Acc", "formula": "({nominal} * {acc_percent} / 100) / sqrt(3)"},
                {"name": "Resolution", "formula": "({resolution} / 2) / sqrt(3)"}
            ],
            "inputs": [
                {"key": "master_uncert", "label": "Master Uncertainty (k=2)", "default": "0.0003"},
                {"key": "acc_percent", "label": "Master Accuracy (%)", "default": "0.001"},
                {"key": "resolution", "label": "Resolution", "default": "0.00001"}
            ]
        },
        # 3. ET: 1 kHz Frequency
        {
            "name": "ET - Frequency (1 kHz)", "unit": "Hz",
            "formulas": [
                {"name": "Master Cert (0.006%)", "formula": "(0.006 * {nominal} / 100) / 2"},
                {"name": "Master Acc", "formula": "((25 * {nominal} / 1000000) + 0.000001) / sqrt(3)"},
                {"name": "Resolution", "formula": "(0.000001 / 2) / sqrt(3)"}
            ],
            "inputs": []
        },
        # 4. Pressure: 30 Bar
        {
            "name": "Pressure - 30 Bar", "unit": "Bar",
            "formulas": [
                {"name": "Master Accuracy", "formula": "{master_acc} / sqrt(3)"},
                {"name": "Master Uncert", "formula": "{master_uncert} / 2"},
                {"name": "Hysteresis", "formula": "{hysteresis} / sqrt(3)"},
                {"name": "Resolution", "formula": "({resolution} / 2) / sqrt(3)"},
                {"name": "Zero Error", "formula": "{zero_error} / sqrt(3)"}
            ],
            "inputs": [
                {"key": "master_acc", "label": "Master Accuracy", "default": "0.035"},
                {"key": "master_uncert", "label": "Master Uncertainty", "default": "0.01"},
                {"key": "hysteresis", "label": "Hysteresis", "default": "0.002"},
                {"key": "resolution", "label": "Resolution", "default": "0.001"},
                {"key": "zero_error", "label": "Zero Error", "default": "0.003"}
            ]
        },
        # 5. Pressure: Vacuum (-0.9 Bar)
        {
            "name": "Pressure - Vacuum (-0.9 Bar)", "unit": "Bar",
            "formulas": [
                {"name": "Master Accuracy", "formula": "{master_acc} / sqrt(3)"},
                {"name": "Master Uncert", "formula": "{master_uncert} / 2"},
                {"name": "Hysteresis", "formula": "{hysteresis} / sqrt(3)"},
                {"name": "Resolution", "formula": "({resolution} / 2) / sqrt(3)"},
                {"name": "Zero Error", "formula": "{zero_error} / sqrt(3)"}
            ],
            "inputs": [
                {"key": "master_acc", "label": "Master Accuracy", "default": "0.0005"},
                {"key": "master_uncert", "label": "Master Uncertainty", "default": "0.00029"},
                {"key": "hysteresis", "label": "Hysteresis", "default": "0.0001"},
                {"key": "resolution", "label": "Resolution", "default": "0.001"},
                {"key": "zero_error", "label": "Zero Error", "default": "0.0001"}
            ]
        },
        # 6. Thermal: Glass Thermometer
        {
            "name": "Thermal - Glass Thermometer", "unit": "°C",
            "formulas": [
                {"name": "Bath Stability", "formula": "{stability} / sqrt(3)"},
                {"name": "Bath Uniformity", "formula": "{uniformity} / sqrt(3)"},
                {"name": "Master Uncert", "formula": "{master_uncert} / 2"},
                {"name": "Drift of Master", "formula": "({master_uncert} * 0.10) / sqrt(3)"},
                {"name": "Resolution", "formula": "({resolution} / 2) / sqrt(3)"}
            ],
            "inputs": [
                {"key": "stability", "label": "Bath Stability", "default": "0.02"},
                {"key": "uniformity", "label": "Bath Uniformity", "default": "0.04"},
                {"key": "master_uncert", "label": "Master Uncert", "default": "0.1"},
                {"key": "resolution", "label": "Resolution", "default": "0.1"}
            ]
        },
        # 7. Thermal: Thermocouple (N-Type)
        {
            "name": "Thermal - Thermocouple N-Type", "unit": "°C",
            "formulas": [
                {"name": "Stability", "formula": "{stability} / sqrt(3)"},
                {"name": "Uniformity", "formula": "{uniformity} / sqrt(3)"},
                {"name": "Master Uncert", "formula": "{master_uncert} / 2"},
                {"name": "Drift", "formula": "({master_uncert} * 0.10) / sqrt(3)"},
                {"name": "Readout Unit", "formula": "{readout} / 2"},
                {"name": "Resolution", "formula": "({resolution} / 2) / sqrt(3)"},
                {"name": "In-homogeneity", "formula": "({nominal} * 0.05 / 100) / sqrt(3)"}
            ],
            "inputs": [
                {"key": "stability", "label": "Stability", "default": "0.46"},
                {"key": "uniformity", "label": "Uniformity", "default": "0.53"},
                {"key": "master_uncert", "label": "Master Uncert", "default": "1.47"},
                {"key": "readout", "label": "Readout Unit", "default": "0"},
                {"key": "resolution", "label": "Resolution", "default": "0.1"}
            ]
        },
        # 8. Mechanical: Digital Caliper
        {
            "name": "Mechanical - Digital Caliper", "unit": "mm",
            "formulas": [
                {"name": "Resolution", "formula": "({resolution} / 2) / sqrt(3)"},
                {"name": "Master Uncert", "formula": "{master_uncert} / 1.96"},
                {"name": "Master Acc", "formula": "{master_acc} / sqrt(3)"},
                {"name": "Temp Monitoring", "formula": "({coeff} * {nominal} * 0.45) / sqrt(3) * 1000"},
                {"name": "Temp Error", "formula": "({coeff} * {nominal} * 0.2) / sqrt(3) * 1000"},
                {"name": "Temp Deviation", "formula": "({coeff} * {nominal} * {temp_diff}) / sqrt(3) * 1000"}
            ],
            "inputs": [
                {"key": "resolution", "label": "Resolution", "default": "0.01"},
                {"key": "master_uncert", "label": "Master Uncert", "default": "1.52"},
                {"key": "master_acc", "label": "Master Acc", "default": "1.4"},
                {"key": "coeff", "label": "Thermal Expansion Coeff", "default": "0.0000115"},
                {"key": "temp_diff", "label": "Temp Difference (from 20°C)", "default": "0.5"}
            ]
        },
        # 9. Mechanical: Bore Gauge
        {
            "name": "Mechanical - Bore Gauge", "unit": "mm",
            "formulas": [
                {"name": "Resolution of Master", "formula": "(0.1 / 2) / sqrt(3)"},
                {"name": "Master Uncert", "formula": "{master_uncert} / 2"},
                {"name": "Master Acc", "formula": "{master_acc} / sqrt(3)"},
                {"name": "Temp Monitoring", "formula": "({coeff} * {nominal} * 0.45) / sqrt(3) * 1000"},
                {"name": "Temp Error", "formula": "({coeff} * {nominal} * 0.2) / sqrt(3) * 1000"},
                {"name": "Temp Deviation", "formula": "({coeff} * {nominal} * {temp_diff}) / sqrt(3) * 1000"}
            ],
            "inputs": [
                {"key": "master_uncert", "label": "Master Uncert", "default": "0.13"},
                {"key": "master_acc", "label": "Master Acc", "default": "0.42"},
                {"key": "coeff", "label": "Thermal Expansion Coeff", "default": "0.0000115"},
                {"key": "temp_diff", "label": "Temp Difference", "default": "0.5"}
            ]
        },
        # 10. Mechanical: Weighing Balance (500g)
        {
            "name": "Mechanical - Weighing Balance", "unit": "g",
            "formulas": [
                {"name": "Eccentricity", "formula": "({mpe} * 0.1) / (2 * sqrt(3))"},
                {"name": "Std Weight Uncert", "formula": "{master_uncert} / 2"},
                {"name": "Drift of Std", "formula": "({master_uncert} * 0.1) / sqrt(3)"},
                {"name": "Resolution", "formula": "({resolution} / 2) / sqrt(3)"}
            ],
            "inputs": [
                {"key": "mpe", "label": "MPE (Max Permissible Error)", "default": "0.00025"},
                {"key": "master_uncert", "label": "Std Weight Uncertainty", "default": "0.0001"},
                {"key": "resolution", "label": "Resolution", "default": "0.001"}
            ]
        },
        # 11. Mechanical: Micro Pipette
        {
            "name": "Mechanical - Micro Pipette", "unit": "µl",
            "formulas": [
                {"name": "Balance Uncert", "formula": "{balance_uncert} / 2"},
                {"name": "Evaporation Loss", "formula": "{evaporation} / sqrt(3)"},
                {"name": "Water Temp", "formula": "(({t_after} - {t_before}) / sqrt(3)) * 0.02"},
                {"name": "Thermometer", "formula": "({thermo} / 2) * 0.00045"},
                {"name": "Barometer", "formula": "({baro} / 2) * 0.00012"},
                {"name": "Hygrometer", "formula": "({hygro} / 2) * 0.00001"},
                {"name": "Cubical Expansion", "formula": "(({t_after} - {t_before}) / sqrt(3)) * 0.00024"}
            ],
            "inputs": [
                {"key": "balance_uncert", "label": "Balance Uncertainty", "default": "0.00004"},
                {"key": "evaporation", "label": "Evaporation Loss", "default": "0.7"},
                {"key": "t_before", "label": "Water Temp Before", "default": "20.1"},
                {"key": "t_after", "label": "Water Temp After", "default": "20.2"},
                {"key": "thermo", "label": "Thermometer Uncert", "default": "0.45"},
                {"key": "baro", "label": "Barometer Uncert", "default": "0.7"},
                {"key": "hygro", "label": "Hygrometer Uncert", "default": "1.54"}
            ]
        },
        # 12. Mechanical: Bevel Protractor
        {
            "name": "Mechanical - Bevel Protractor", "unit": "deg",
            "formulas": [
                {"name": "Master Uncert", "formula": "(1.8 / 60) / 2"},
                {"name": "Master Acc", "formula": "(0.9 / 60) / sqrt(3)"},
                {"name": "Resolution", "formula": "(5 / 2) / sqrt(3)"}
            ],
            "inputs": []
        },
        # 13. Mechanical: Coating Thickness
        {
            "name": "Mechanical - Coating Thickness", "unit": "µm",
            "formulas": [
                {"name": "Resolution", "formula": "(1 / 2) / sqrt(3)"},
                {"name": "Master Uncert", "formula": "{master_uncert} / 2"},
                {"name": "Comparator Uncert", "formula": "2.1 / 2"},
                {"name": "Temp Monitoring", "formula": "({coeff} * {nominal} * 0.45) / sqrt(3) * 1000"},
                {"name": "Temp Error", "formula": "({coeff} * {nominal} * 0.2) / sqrt(3) * 1000"},
                {"name": "Temp Deviation", "formula": "({coeff} * {nominal} * {temp_diff}) / sqrt(3) * 1000"}
            ],
            "inputs": [
                {"key": "master_uncert", "label": "Master Uncert", "default": "1.1"},
                {"key": "coeff", "label": "Thermal Expansion Coeff", "default": "0.00007"},
                {"key": "temp_diff", "label": "Temp Difference", "default": "0.5"}
            ]
        },
        # 14. RPM: Tachometer
        {
            "name": "RPM - Tachometer", "unit": "RPM",
            "formulas": [
                {"name": "Master Uncert", "formula": "{master_uncert} / 1.96"},
                {"name": "Master Acc", "formula": "(({nominal} * 0.01 / 100) + {offset}) / 1.73"},
                {"name": "Source Acc", "formula": "{source_acc} / 1.73"},
                {"name": "Resolution", "formula": "({resolution} / 2) / 1.73"}
            ],
            "inputs": [
                {"key": "master_uncert", "label": "Master Uncert", "default": "15"},
                {"key": "offset", "label": "Master Offset", "default": "1"},
                {"key": "source_acc", "label": "Source Accuracy", "default": "5"},
                {"key": "resolution", "label": "Resolution", "default": "0.1"}
            ]
        },
        # 15. Acoustics: Sound Level Meter
        {
            "name": "Acoustics - Sound Level Meter", "unit": "dB",
            "formulas": [
                {"name": "Master Uncert", "formula": "{master_uncert} / 1.96"},
                {"name": "Master Acc", "formula": "{master_acc} / 1.73"},
                {"name": "Resolution", "formula": "({resolution} / 2) / 1.73"}
            ],
            "inputs": [
                {"key": "master_uncert", "label": "Master Uncert", "default": "0.41"},
                {"key": "master_acc", "label": "Master Acc", "default": "0.3"},
                {"key": "resolution", "label": "Resolution", "default": "0.1"}
            ]
        }
    ]

    # Insert all templates into DB
    for t in master_templates:
        cur.execute("INSERT INTO templates (name, unit, formula_json, input_schema) VALUES (%s, %s, %s, %s)", 
                    (t["name"], t["unit"], json.dumps({"components": t["formulas"]}), json.dumps(t["inputs"])))
    
    conn.commit()

    cur.execute("SELECT id, name, unit, input_schema FROM templates")
    template_list = [{"id": row[0], "name": row[1], "unit": row[2], "schema": json.loads(row[3])} for row in cur.fetchall()]
    cur.close()
    conn.close()
    
    return templates.TemplateResponse(request=request, name="index.html", context={"templates": template_list, "templates_json": json.dumps(template_list)})

@app.post("/calculate")
def calculate_and_save(req: CalcRequest):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT formula_json, unit FROM templates WHERE id = %s", (req.template_id,))
        row = cur.fetchone()
        tpl_data = json.loads(row[0])
        unit = row[1]

        # 1. Calculate Type A (Repeatability)
        n = len(req.readings_test)
        if n < 2: return {"error": "Need at least 2 readings."}
        
        stdev_master = statistics.stdev(req.readings_master) if len(req.readings_master) > 1 else 0
        stdev_test = statistics.stdev(req.readings_test) if len(req.readings_test) > 1 else 0
        max_stdev = max(stdev_master, stdev_test)
        ua = max_stdev / math.sqrt(n)
        
        budget = [{"name": "Ua: Repeatability (Type A)", "u": ua, "formula": "MAX(SD_Master, SD_Test)/sqrt(n)"}]
        sum_variance = ua**2

        # 2. Dynamic Context mapping
        context = {"nominal": req.nominal_value}
        context.update(req.variables) 
        
        for comp in tpl_data["components"]:
            formula = comp["formula"]
            for key, val in context.items():
                formula = formula.replace(f"{{{key}}}", str(val))
            
            u_comp = eval(formula, {"__builtins__": {}}, {"sqrt": math.sqrt})
            sum_variance += u_comp**2
            budget.append({"name": comp["name"], "u": u_comp, "formula": comp["formula"]})

        # 3. Final calculations
        uc = math.sqrt(sum_variance)
        U = uc * 2

        # 4. Save to DB
        cur.execute("""
            CREATE TABLE IF NOT EXISTS calculations (
                id SERIAL PRIMARY KEY,
                template_id INT,
                nominal_value FLOAT,
                uc FLOAT,
                U FLOAT
            )
        """)
        cur.execute("INSERT INTO calculations (template_id, nominal_value, uc, U) VALUES (%s, %s, %s, %s)",
                    (req.template_id, req.nominal_value, uc, U))
        conn.commit()
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

    # 5. GENERATE PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>AQCAL MEASUREMENTS (OPC) PRIVATE LIMITED</b>", styles["Title"]))
    story.append(Paragraph("Certificate of Calibration (Uncertainty Budget)", styles["Heading2"]))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph(f"<b>Nominal Value:</b> {req.nominal_value} {unit}", styles["Normal"]))
    story.append(Paragraph(f"<b>Combined Standard Uncertainty (uc):</b> {uc:.6f} {unit}", styles["Normal"]))
    story.append(Paragraph(f"<b>Expanded Uncertainty (U) [k=2]:</b> {U:.6f} {unit}", styles["Normal"]))
    story.append(Spacer(1, 12))

    data = [["Source of Uncertainty", "Standard Uncertainty (u)", "Formula Used"]]
    data.append(["Type A: Repeatability", f"{ua:.6f}", "MAX(SD_M, SD_T) / sqrt(n)"])
    for item in budget[1:]:
        data.append([item["name"], f"{item['u']:.6f}", item["formula"]])

    table = Table(data, colWidths=[180, 120, 200])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)
    story.append(Spacer(1, 24))
    story.append(Paragraph("Generated automatically by AQCAL LIMS.", styles["Italic"]))

    doc.build(story)
    pdf_buffer.seek(0)

    return Response(content=pdf_buffer.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=Certificate.pdf"})
