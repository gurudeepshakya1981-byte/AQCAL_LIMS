from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import os
import psycopg2
from pydantic import BaseModel

app = FastAPI(title="AQCAL LIMS")
templates = Jinja2Templates(directory="templates")

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

class CalcRequest(BaseModel):
    u1: float
    u2: float
    u3: float
    u4: float

# This serves the beautiful HTML page
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/calculate")
def calculate_and_save(req: CalcRequest):
    uc = (req.u1**2 + req.u2**2 + req.u3**2 + req.u4**2) ** 0.5
    U = uc * 2
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS calculations (
                id SERIAL PRIMARY KEY,
                uc FLOAT,
                expanded_uncertainty FLOAT
            )
        """)
        cur.execute(
            "INSERT INTO calculations (uc, expanded_uncertainty) VALUES (%s, %s)",
            (uc, U)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return {"error": str(e)}

    return {
        "combined_uncertainty": uc, 
        "expanded_uncertainty": U,
        "message": "Successfully saved!"
    }