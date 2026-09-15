from fastapi import FastAPI

app = FastAPI(
    title="BIGBAND Influencer Search API",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "service": "BIGBAND Influencer Search API",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }