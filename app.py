# ✅ main.py (FastAPI Application)

import os
import uuid
import shutil
import boto3
from fastapi import FastAPI, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from PIL import Image
from ultralytics import YOLO
from dotenv import load_dotenv
from sqlite_storage import SQLiteStorage
from dynamodb_storage import DynamoDBStorage
from init_db import init_db

load_dotenv()

S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET")
S3_CLIENT = boto3.client("s3")

UPLOAD_DIR = "uploads/original"
PREDICTED_DIR = "uploads/predicted"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREDICTED_DIR, exist_ok=True)

model = YOLO("yolov8n.pt")
app = FastAPI()

# Choose storage implementation
storage_type = os.getenv("STORAGE_TYPE", "sqlite")
if storage_type == "dynamodb":
    storage = DynamoDBStorage()
else:
    init_db()
    storage = SQLiteStorage()

@app.post("/predict")
async def predict(request: Request):
    try:
        form = await request.form()
        uid = str(uuid.uuid4())
        local_output_path = os.path.join(PREDICTED_DIR, uid + ".jpg")

        if "file" in form:
            file = form["file"]
            file_name = file.filename
            local_input_path = os.path.join(UPLOAD_DIR, file_name)
            with open(local_input_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

        elif "s3_key" in form:
            s3_key = form["s3_key"]
            local_input_path = os.path.join(UPLOAD_DIR, s3_key)
            S3_CLIENT.download_file(S3_BUCKET_NAME, s3_key, local_input_path)
        else:
            raise HTTPException(status_code=400, detail="No file or S3 key provided")

        results = model(local_input_path, device="cpu")

        annotated_frame = results[0].plot()
        annotated_image = Image.fromarray(annotated_frame)
        annotated_image.save(local_output_path)

        annotated_s3_key = f"predictions/{uid}_annotated.jpg"
        with open(local_output_path, "rb") as f:
            S3_CLIENT.upload_fileobj(f, S3_BUCKET_NAME, annotated_s3_key)

        storage.save_prediction(uid, local_input_path, local_output_path)

        detected_labels = []
        for box in results[0].boxes:
            label_idx = int(box.cls[0].item())
            label = model.names[label_idx]
            score = float(box.conf[0])
            bbox = box.xyxy[0].tolist()
            storage.save_detection(uid, label, score, bbox)
            detected_labels.append(label)

        return {
            "prediction_uid": uid,
            "detection_count": len(results[0].boxes),
            "labels": detected_labels
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

@app.get("/prediction/{uid}/image")
def get_prediction_image(uid: str, request: Request):
    accept = request.headers.get("accept", "")
    prediction = storage.get_prediction(uid)
    image_path = prediction.get("predicted_image")

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Predicted image file not found")

    if "image/png" in accept:
        return FileResponse(image_path, media_type="image/png")
    elif "image/jpeg" in accept or "image/jpg" in accept:
        return FileResponse(image_path, media_type="image/jpeg")
    else:
        raise HTTPException(status_code=406, detail="Client does not accept an image format")

@app.get("/image/{type}/{filename}")
def get_image(type: str, filename: str):
    if type not in ["original", "predicted"]:
        raise HTTPException(status_code=400, detail="Invalid image type")
    path = os.path.join("uploads", type, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)

@app.get("/prediction/{uid}")
def get_prediction(uid: str):
    return storage.get_prediction(uid)

@app.get("/predictions/label/{label}")
def get_predictions_by_label(label: str):
    return storage.get_predictions_by_label(label)

@app.get("/predictions/score/{min_score}")
def get_predictions_by_score(min_score: float):
    return storage.get_predictions_by_score(min_score)

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)