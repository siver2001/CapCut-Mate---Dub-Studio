from pydantic import BaseModel, Field, HttpUrl

class GetAudioDurationRequest(BaseModel):
    """Getaudiodurationrequest parameters"""
    mp3_url: HttpUrl = Field(..., description='audioURL，mp3、wav、m4aaudio')

class Config:
    json_schema_extra = {'example': {'mp3_url': 'https://www.soundjay.com/misc/sounds/bell-ringing-05.wav'}}

class GetAudioDurationResponse(BaseModel):
    """Getaudiodurationresponse parameters"""
    duration: int = Field(..., description='audioduration，：microseconds', ge=0)

class Config:
    json_schema_extra = {'example': {'duration': 2325333}}