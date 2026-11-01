import uvicorn

def main() -> None:
    uvicorn.run("gridmind.main:app", host="0.0.0.0", port=8000, reload=True)
