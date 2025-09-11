import sqlite3
from typing import List, Dict
from storage_interface import StorageInterface

DB_PATH = "predictions.db"

class SQLiteStorage(StorageInterface):
    def save_prediction(self, uid: str, original_path: str, predicted_path: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, original_image, predicted_image)
                VALUES (?, ?, ?)
            """, (uid, original_path, predicted_path))

    def save_detection(self, uid: str, label: str, score: float, bbox: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO detection_objects (prediction_uid, label, score, box)
                VALUES (?, ?, ?, ?)
            """, (uid, label, score, str(bbox)))

    def get_prediction(self, uid: str) -> Dict:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            session = conn.execute("SELECT * FROM prediction_sessions WHERE uid = ?", (uid,)).fetchone()
            objects = conn.execute("SELECT * FROM detection_objects WHERE prediction_uid = ?", (uid,)).fetchall()
            return {
                "uid": session["uid"],
                "timestamp": session["timestamp"],
                "original_image": session["original_image"],
                "predicted_image": session["predicted_image"],
                "detection_objects": [
                    {"id": o["id"], "label": o["label"], "score": o["score"], "box": o["box"]}
                    for o in objects
                ]
            }

    def get_predictions_by_label(self, label: str) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT DISTINCT ps.uid, ps.timestamp
                FROM prediction_sessions ps
                JOIN detection_objects do ON ps.uid = do.prediction_uid
                WHERE do.label = ?
            """, (label,)).fetchall()
            return [{"uid": row["uid"], "timestamp": row["timestamp"]} for row in rows]

    def get_predictions_by_score(self, min_score: float) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT DISTINCT ps.uid, ps.timestamp
                FROM prediction_sessions ps
                JOIN detection_objects do ON ps.uid = do.prediction_uid
                WHERE do.score >= ?
            """, (min_score,)).fetchall()
            return [{"uid": row["uid"], "timestamp": row["timestamp"]} for row in rows]

