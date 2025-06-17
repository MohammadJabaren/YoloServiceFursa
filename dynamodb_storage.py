import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from storage_interface import StorageInterface
import json
from typing import List, Dict
import os


class DynamoDBStorage(StorageInterface):
    def __init__(self):
        region = os.getenv("AWS_REGION", "us-west-1")  # default to us-west-1 if not set
        if not region:
            raise ValueError("Missing AWS_REGION environment variable")
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.session_table = self.dynamodb.Table("Jabaren_prediction_sessions_dev")
        self.objects_table = self.dynamodb.Table("Jabaren_detection_objects_dev")

    def save_prediction(self, uid: str, original_path: str, predicted_path: str):
        self.session_table.put_item(Item={
            "uid": uid,
            "original_image": original_path,
            "predicted_image": predicted_path
        })

    def save_detection(self, uid: str, label: str, score: float, bbox: str):
        item = {
            "prediction_uid": uid,
            "label_score": f"{label}#{score}",
            "label": label,
            "score": score,
            "score_partition": "score",
            "box": str(bbox)
        }
        self.objects_table.put_item(Item=item)


    def get_prediction(self, uid: str) -> Dict:
        session = self.session_table.get_item(Key={"uid": uid}).get("Item")
        if not session:
            raise ValueError("Prediction not found")
        response = self.objects_table.query(
            KeyConditionExpression=Key("prediction_uid").eq(uid)
        )
        return {
            "uid": uid,
            "original_image": session.get("original_image"),
            "predicted_image": session.get("predicted_image"),
            "detection_objects": [
                {
                    "label": item["label"],
                    "score": float(item["score"]),
                    "box": json.loads(item["box"])
                } for item in response.get("Items", [])
            ]
        }

    def get_predictions_by_label(self, label: str) -> List[Dict]:
        response = self.objects_table.query(
            IndexName="LabelScoreIndex",
            KeyConditionExpression=Key("label").eq(label)
        )
        seen = set()
        result = []
        for item in response["Items"]:
            uid = item["prediction_uid"]
            if uid not in seen:
                seen.add(uid)
                session = self.session_table.get_item(Key={"uid": uid}).get("Item")
                result.append({"uid": uid, "timestamp": session.get("timestamp", "unknown")})
        return result


    def get_predictions_by_score(self, min_score: float) -> List[Dict]:
        response = self.objects_table.query(
            IndexName="ScoreIndex",
            KeyConditionExpression=Key("score_partition").eq("score") & Key("score").gte(Decimal(str(min_score)))
        )
        seen = set()
        result = []
        for item in response["Items"]:
            uid = item["prediction_uid"]
            if uid not in seen:
                seen.add(uid)
                session = self.session_table.get_item(Key={"uid": uid}).get("Item")
                result.append({"uid": uid, "timestamp": session.get("timestamp", "unknown")})
        return result

#test