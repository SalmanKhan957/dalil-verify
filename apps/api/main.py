from fastapi import FastAPI

app = FastAPI(title='Dalil Verify API')

@app.get('/health')
def health():
    return {'status': 'ok'}
