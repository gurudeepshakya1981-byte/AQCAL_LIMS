from fastapi import FastAPI

app = FastAPI(title="AQCAL LIMS")

@app.get("/")
def read_root():
    return {"status": "Success", "message": "AQCAL LIMS Backend is Live!"}

@app.get("/calculate")
def calculate_test():
    # Validated data from your 10 MΩ Excel sheet
    u1 = 0.00025
    u2 = 0.003464
    u3 = 0.00000288
    u4 = 0.0000066
    
    uc = (u1**2 + u2**2 + u3**2 + u4**2) ** 0.5
    U = uc * 2
    
    return {"combined_uncertainty": uc, "expanded_uncertainty": U}