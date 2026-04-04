from uvicorn import run


if __name__ == "__main__":
    run("apps.public_api.main:app", reload=True)
