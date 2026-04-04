from pydantic import BaseModel

class Settings(BaseModel):
    app_name: str = 'Dalil Verify'
    env: str = 'development'

settings = Settings()
