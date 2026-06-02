import cloudinary
import cloudinary.uploader

from dotenv import load_dotenv

import os

load_dotenv()

cloudinary.config(

    cloud_name=os.getenv("CLOUD_NAME"),

    api_key=os.getenv("API_KEY"),

    api_secret=os.getenv("API_SECRET"),

    secure=True

)


def upload_resume(file):

    result = cloudinary.uploader.upload(

        file,

        folder="resumes",

        resource_type="raw"

    )

    return {

        "url": result["secure_url"],

        "public_id": result["public_id"]

    }