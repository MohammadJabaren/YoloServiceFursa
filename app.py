import boto3
import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse
from ultralytics import YOLO
from PIL import Image
import sqlite3
from pydantic import BaseModel
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# AWS S3 settings
S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET")
S3_CLIENT = boto3.client("s3")
app = FastAPI()

# Set up directories
UPLOAD_DIR = "uploads/original"
PREDICTED_DIR = "uploads/predicted"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREDICTED_DIR, exist_ok=True)

# YOLO model
model = YOLO("yolov8n.pt")

# Initialize SQLite
DB_PATH = "predictions.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        # Create the predictions main table to store the prediction session
        conn.execute("""
                     CREATE TABLE IF NOT EXISTS prediction_sessions
                     (
                         uid
                         TEXT
                         PRIMARY
                         KEY,
                         timestamp
                         DATETIME
                         DEFAULT
                         CURRENT_TIMESTAMP,
                         original_image
                         TEXT,
                         predicted_image
                         TEXT
                     )
                     """)

        # Create the objects table to store individual detected objects in a given image
        conn.execute("""
                     CREATE TABLE IF NOT EXISTS detection_objects
                     (
                         id
                         INTEGER
                         PRIMARY
                         KEY
                         AUTOINCREMENT,
                         prediction_uid
                         TEXT,
                         label
                         TEXT,
                         score
                         REAL,
                         box
                         TEXT,
                         FOREIGN
                         KEY
                     (
                         prediction_uid
                     ) REFERENCES prediction_sessions
                     (
                         uid
                     )
                         )
                     """)

        # Create index for faster queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prediction_uid ON detection_objects (prediction_uid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_label ON detection_objects (label)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_score ON detection_objects (score)")


init_db()

def save_detection_object(uid, label, score, bbox):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO detection_objects (prediction_uid, label, score, box)
                VALUES (?, ?, ?, ?)
            """, (uid, label, score, str(bbox)))
    except Exception as e:
        logger.error(f"Error saving detection: {str(e)}")


def save_prediction_session(uid, original_path, predicted_s3_path):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, original_image, predicted_image)
                VALUES (?, ?, ?)
            """, (uid, original_path, predicted_s3_path))
    except Exception as e:
        logger.error(f"Error saving prediction session: {str(e)}")


@app.post("/predict")
async def predict(request: Request):
    try:
        # First, check if the request contains a file
        form = await request.form()
        uid = str(uuid.uuid4())
        local_output_path = os.path.join(PREDICTED_DIR, uid + ".jpg")
        if "file" in form:
            file = form["file"]
            file_name = file.filename
            local_input_path = os.path.join(UPLOAD_DIR, file_name)

            # Save the file locally
            with open(local_input_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

        elif "s3_key" in form:  # Check for s3_key if no file is uploaded
            s3_key = form["s3_key"]
            local_input_path = os.path.join(UPLOAD_DIR, s3_key)
            # Download image from S3 (Add your S3 download logic here)
            S3_CLIENT.download_file(S3_BUCKET_NAME, s3_key, local_input_path)
        else:
            raise HTTPException(status_code=400, detail="No file or S3 key provided")

        # Now, you can proceed with the image processing (YOLO model)
        # Process the image here (YOLO inference, annotation, etc.)
        results = model(local_input_path, device="cpu")

        # Step 3: Annotate result
        annotated_frame = results[0].plot()
        annotated_image = Image.fromarray(annotated_frame)
        annotated_image.save(local_output_path)

        # Step 4: Upload annotated image to S3
        annotated_s3_key = f"predictions/{uid}_annotated.jpg"
        with open(local_output_path, "rb") as f:
            S3_CLIENT.upload_fileobj(f, S3_BUCKET_NAME, annotated_s3_key)

        # Step 5: Save prediction session
        save_prediction_session(uid, local_input_path, local_output_path)

        # Step 6: Save detections
        detected_labels = []
        for box in results[0].boxes:
            label_idx = int(box.cls[0].item())
            label = model.names[label_idx]
            score = float(box.conf[0])
            bbox = box.xyxy[0].tolist()
            save_detection_object(uid, label, score, bbox)
            detected_labels.append(label)

        return {
            "prediction_uid": uid,
            "detection_count": len(results[0].boxes),
            "labels": detected_labels
        }

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

@app.get("/prediction/{uid}")
def get_prediction_by_uid(uid: str):
    """
    Get prediction session by uid with all detected objects
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        # Get prediction session
        session = conn.execute("SELECT * FROM prediction_sessions WHERE uid = ?", (uid,)).fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Prediction not found")
            
        # Get all detection objects for this prediction
        objects = conn.execute(
            "SELECT * FROM detection_objects WHERE prediction_uid = ?", 
            (uid,)
        ).fetchall()
        
        return {
            "uid": session["uid"],
            "timestamp": session["timestamp"],
            "original_image": session["original_image"],
            "predicted_image": session["predicted_image"],
            "detection_objects": [
                {
                    "id": obj["id"],
                    "label": obj["label"],
                    "score": obj["score"],
                    "box": obj["box"]
                } for obj in objects
            ]
        }

@app.get("/predictions/label/{label}")
def get_predictions_by_label(label: str):
    """
    Get prediction sessions containing objects with specified label
    """
    valid_labels = list(model.names.values())
    if label not in valid_labels:
        raise HTTPException(status_code=404, detail="Invalid label")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT DISTINCT ps.uid, ps.timestamp
            FROM prediction_sessions ps
            JOIN detection_objects do ON ps.uid = do.prediction_uid
            WHERE do.label = ?
        """, (label,)).fetchall()
        
        return [{"uid": row["uid"], "timestamp": row["timestamp"]} for row in rows]

@app.get("/predictions/score/{min_score}")
def get_predictions_by_score(min_score: float):
    """
    Get prediction sessions containing objects with score >= min_score
    """
    if not (0.0 <= min_score <= 1.0):
        raise HTTPException(status_code=400, detail="Score must be between 0 and 1")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT DISTINCT ps.uid, ps.timestamp
            FROM prediction_sessions ps
            JOIN detection_objects do ON ps.uid = do.prediction_uid
            WHERE do.score >= ?
        """, (min_score,)).fetchall()
        
        return [{"uid": row["uid"], "timestamp": row["timestamp"]} for row in rows]

@app.get("/image/{type}/{filename}")
def get_image(type: str, filename: str):
    """
    Get image by type and filename
    """
    if type not in ["original", "predicted"]:
        raise HTTPException(status_code=400, detail="Invalid image type")
    path = os.path.join("uploads", type, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)

@app.get("/prediction/{uid}/image")
def get_prediction_image(uid: str, request: Request):
    """
    Get prediction image by uid
    """
    accept = request.headers.get("accept", "")
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT predicted_image FROM prediction_sessions WHERE uid = ?", (uid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Prediction not found")
        image_path = row[0]

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Predicted image file not found")

    if "image/png" in accept:
        return FileResponse(image_path, media_type="image/png")
    elif "image/jpeg" in accept or "image/jpg" in accept:
        return FileResponse(image_path, media_type="image/jpeg")
    else:
        # If the client doesn't accept image, respond with 406 Not Acceptable
        raise HTTPException(status_code=406, detail="Client does not accept an image format")

@app.get("/health")
def health():
    """
    Health check endpoint
    """
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
